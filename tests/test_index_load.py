"""索引加载的契约测试：与 build 结果等价、校验拦截（缺文件 / id 不一致 / 坏行）。"""

import pytest

from ragkit.config import AppConfig
from ragkit.index import build, load_index
from ragkit.retrieval.pipeline import search

QUERY = "容器冷启动"


def _built(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    (root / "a.txt").write_text(
        "容器冷启动 优化指南\n\n冷启动是指容器首次启动时明显变慢的现象。", encoding="utf-8"
    )
    (root / "b.txt").write_text("数据库连接池 的配置方法与参数说明。", encoding="utf-8")
    (root / "bad.md").write_bytes(b"\xff\xfe\x00\x01")
    cfg = AppConfig(index_dir=tmp_path / "idx")
    return build(root, cfg), cfg


def _search(built, retrieval):
    return search(
        QUERY,
        bm25=built.bm25,
        store=built.store,
        id_to_chunk=built.id_to_chunk,
        dim=built.dim,
        retrieval=retrieval,
    )


def test_load_index_matches_build(tmp_path):
    built, cfg = _built(tmp_path)

    loaded = load_index(cfg.index_dir)

    # BM25 从落盘 chunks 重建 → 统计一致 → 同 query 同结果
    first = _search(built, cfg.retrieval)
    second = _search(loaded, cfg.retrieval)
    assert [r.chunk.chunk_id for r in first.results] == [
        r.chunk.chunk_id for r in second.results
    ]
    assert [r.score for r in first.results] == pytest.approx(
        [r.score for r in second.results]
    )


def test_load_index_dim_from_store_and_failures_empty(tmp_path):
    built, cfg = _built(tmp_path)

    loaded = load_index(cfg.index_dir)

    assert loaded.dim == built.store.dim
    assert loaded.failures == []


def test_load_index_missing_chunks_jsonl_raises(tmp_path):
    _, cfg = _built(tmp_path)
    (cfg.index_dir / "chunks.jsonl").unlink()

    with pytest.raises(FileNotFoundError):
        load_index(cfg.index_dir)


def test_load_index_id_mismatch_raises(tmp_path):
    _, cfg = _built(tmp_path)
    p = cfg.index_dir / "chunks.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    # 删掉一行 → chunks 与 store 的 id 集合不一致（半成品索引）
    p.write_text("".join(lines[:-1]), encoding="utf-8")

    with pytest.raises(ValueError, match="两者不一致"):
        load_index(cfg.index_dir)


def test_load_index_corrupt_line_raises(tmp_path):
    _, cfg = _built(tmp_path)
    p = cfg.index_dir / "chunks.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    # 第二行换成坏 JSON → 报错必须带行号定位
    p.write_text(lines[0] + "{bad json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=":2:"):
        load_index(cfg.index_dir)
