"""HTTP API 的契约测试：真服务器 + urllib 集成——端点、错误翻译表、日志。"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from ragkit import __version__
from ragkit.api import create_server
from ragkit.config import AppConfig
from ragkit.index import build


def _make_built(tmp_path, empty=False):
    root = tmp_path / "raw"
    root.mkdir(exist_ok=True)
    if not empty:
        (root / "a.txt").write_text(
            "容器冷启动 优化指南\n\n冷启动是指容器首次启动时明显变慢的现象。",
            encoding="utf-8",
        )
    cfg = AppConfig(index_dir=tmp_path / "idx")
    return build(root, cfg), cfg


@pytest.fixture
def serving(tmp_path):
    """按需启动服务器（port=0 随机分配，互不冲突）；测试结束统一关闭。"""
    made = []

    def _start(empty=False):
        built, cfg = _make_built(tmp_path, empty=empty)
        srv = create_server("127.0.0.1", 0, built, cfg)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        made.append(srv)
        return srv

    yield _start
    for srv in made:
        srv.shutdown()
        srv.server_close()


def _request(srv, path, *, method="GET", data=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{srv.server_address[1]}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _ask(srv, payload):
    return _request(
        srv, "/ask", method="POST", data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )


def test_ask_returns_answer_json(serving):
    srv = serving()

    status, payload = _ask(srv, {"query": "容器冷启动"})

    assert status == 200
    assert payload["question"] == "容器冷启动"
    assert payload["refused"] is False
    assert payload["citations"][0]["source"] == "a.txt"
    assert "冷启动" in payload["answer"]


def test_ask_refused_is_200(serving):
    # 拒答是业务正常结果：200 + refused=true（与 CLI 拒答=退出码 0 同语义）
    srv = serving(empty=True)

    status, payload = _ask(srv, {"query": "任何问题"})

    assert status == 200
    assert payload["refused"] is True
    assert payload["answer"] == ""
    assert payload["citations"] == []


def test_ask_bad_json_returns_400(serving):
    status, payload = _request(
        serving(), "/ask", method="POST", data=b"not json at all"
    )

    assert status == 400
    assert "error" in payload


@pytest.mark.parametrize("payload", [{}, {"query": ""}, {"query": 123}, {"q": "x"}])
def test_ask_invalid_query_returns_400(serving, payload):
    status, body = _ask(serving(), payload)

    assert status == 400
    assert "error" in body


def test_unknown_path_returns_404(serving):
    status, payload = _request(serving(), "/nope", method="POST", data=b"{}")

    assert status == 404
    assert payload["error"] == "not found"


def test_wrong_method_returns_405(serving):
    status, payload = _request(serving(), "/ask", method="PUT", data=b"{}")

    assert status == 405
    assert payload["error"] == "method not allowed"


def test_healthz_returns_status(serving):
    status, payload = _request(serving(), "/healthz")

    assert status == 200
    assert payload["version"] == __version__
    assert payload["status"] == "ok"
    assert payload["chunks"] == 1


def test_get_unknown_returns_404(serving):
    status, payload = _request(serving(), "/nope")

    assert status == 404


def test_request_logged(serving, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="ragkit.api")
    _ask(serving(), {"query": "容器冷启动"})

    assert any("POST /ask | 200" in r.message for r in caplog.records)
