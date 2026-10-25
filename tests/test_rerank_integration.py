"""入口到领域流水线的重排集成：真实临时索引、假模型，无下载或推理。"""

import json
from types import SimpleNamespace

import pytest

from ragkit.api.server import _answer_payload, _search_payload
from ragkit.cli import main
from ragkit.config import AppConfig, RerankConfig, RetrievalConfig
from ragkit.errors import RerankError
from ragkit.evaluation import evaluate, load_qrels
from ragkit.index import build
from ragkit.retrieval import pipeline
from ragkit.schemas import ScoredChunk


QUERY = "容器镜像"
UNKNOWN_QUERY = "UnseenService 容器镜像"
LOGIT = -2.25


@pytest.fixture
def rerank_case(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.txt").write_text(
        "容器镜像优化：构建缓存可以避免重复执行相同的构建步骤。", encoding="utf-8"
    )
    (raw / "b.txt").write_text(
        "容器镜像实践：使用较小的基础镜像可以减少拉取镜像的时间。", encoding="utf-8"
    )
    cfg = AppConfig(
        data_dir=raw,
        index_dir=tmp_path / "idx",
        retrieval=RetrievalConfig(top_k=2, final_k=1, refuse_threshold=0.5),
        rerank=RerankConfig(
            enabled=True, model_name="integration-fake-cross-encoder",
            batch_size=3, max_length=96,
        ),
    )
    built = build(raw, cfg)
    baseline = pipeline.search(
        QUERY, bm25=built.bm25, store=built.store,
        id_to_chunk=built.id_to_chunk, dim=built.dim,
        retrieval=cfg.retrieval.model_copy(update={"final_k": 2}),
    )
    assert len(baseline.results) == 2
    # 假模型提升原融合顺序的最后一块，确保入口实际使用重排结果。
    target = baseline.results[-1].chunk
    calls = []

    def fake_rerank(query, candidates, **kwargs):
        assert kwargs == {
            "final_k": 1, "model_name": cfg.rerank.model_name,
            "batch_size": 3, "max_length": 96,
            "device": "cpu", "local_files_only": True,
        }
        assert len(candidates) == 2
        assert len({candidate.chunk.chunk_id for candidate in candidates}) == 2
        assert all(candidate.stage == "weighted_rrf" for candidate in candidates)
        calls.append((query, [candidate.chunk.chunk_id for candidate in candidates]))
        chosen = candidates[-1]
        return [ScoredChunk(chosen.chunk, LOGIT, "rerank", chosen.sub_scores.copy())]

    monkeypatch.setattr(pipeline, "rerank", fake_rerank)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(json.dumps(cfg.snapshot()), encoding="utf-8")
    qrels_path = tmp_path / "qrels.json"
    qrels_path.write_text(json.dumps([
        {
            "query": QUERY, "annotation_version": 2,
            "answers": [{"point": "临时文档中的镜像建议", "evidence": [{
                "doc": target.doc_id, "section": "",
                "start": target.metadata["char_start"],
                "end": target.metadata["char_end"], "quote": target.text,
            }]}],
        },
        {
            "query": UNKNOWN_QUERY, "type": "no_answer", "annotation_version": 2,
            "unanswerable_reason": "临时语料没有该服务的信息", "answers": [],
        },
    ], ensure_ascii=False), encoding="utf-8")
    return SimpleNamespace(
        cfg=cfg, built=built, baseline=baseline, target=target, calls=calls,
        config_path=config_path, qrels_path=qrels_path,
    )


def test_cli_ask_uses_configured_reranker(rerank_case, capsys):
    case = rerank_case

    rc = main(["ask", QUERY, "--config", str(case.config_path)], environ={})

    output = capsys.readouterr()
    assert rc == 0
    assert output.err == ""
    assert case.target.text in output.out
    assert f"[1] {case.target.source}" in output.out
    assert "未找到相关内容" not in output.out
    assert case.calls == [(QUERY, [item.chunk.chunk_id for item in case.baseline.results])]


def test_cli_eval_records_rerank_configuration_and_order(rerank_case, tmp_path):
    case = rerank_case
    out = tmp_path / "report.json"

    rc = main([
        "eval", "--config", str(case.config_path),
        "--qrels", str(case.qrels_path), "--out", str(out),
    ], environ={})

    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["config"]["rerank"]["enabled"] is True
    assert report["config"]["rerank"]["model_name"] == case.cfg.rerank.model_name
    assert report["config"]["retrieval"]["fusion_method"] == "weighted_rrf"
    assert report["per_query"][0]["retrieved"] == [case.target.chunk_id]
    assert report["recall_at"]["1"] == 1.0
    assert report["refusal"]["accuracy"] == 1.0
    assert report["refusal"]["false_rate"] == 0.0
    assert [query for query, _ in case.calls] == [QUERY, UNKNOWN_QUERY]


def test_api_payloads_preserve_negative_logit_and_bm25_refusal(rerank_case):
    case = rerank_case

    answer = _answer_payload(QUERY, case.built, case.cfg)
    search = _search_payload(QUERY, case.built, case.cfg)

    assert answer["answer"] == case.target.text
    assert answer["confidence"] == LOGIT
    assert answer["refused"] is False
    assert [stage["name"] for stage in answer["trace"]["stages"]] == [
        "bm25", "dense", "fusion", "rerank",
    ]
    assert search["results"][0]["chunk_id"] == case.target.chunk_id
    assert search["results"][0]["score"] == LOGIT
    assert search["results"][0]["stage"] == "rerank"
    assert search["match_score"] == case.baseline.match_score
    assert search["match_score"] >= case.cfg.retrieval.refuse_threshold
    assert search["refused"] is False

    # 原有语料外实体拒答仍生效；模型返回非空候选也不能绕过它。
    missing_answer = _answer_payload(UNKNOWN_QUERY, case.built, case.cfg)
    missing_search = _search_payload(UNKNOWN_QUERY, case.built, case.cfg)
    assert missing_answer["refused"] is True
    assert missing_answer["answer"] == ""
    assert missing_search["match_score"] == 0.0
    assert missing_search["refused"] is True
    assert missing_search["results"][0]["score"] == LOGIT
    assert len(case.calls) == 4


def test_evaluate_uses_model_order_and_keeps_independent_match_score(rerank_case):
    case = rerank_case

    report = evaluate(case.built, case.cfg, load_qrels(case.qrels_path))

    hit, missing = report.per_query
    assert hit.retrieved == [case.target.chunk_id]
    assert hit.recall_at[1] == 1.0
    assert hit.match_score == case.baseline.match_score
    assert hit.refused is False
    assert missing.match_score == 0.0
    assert missing.refused is True
    assert report.config["rerank"] == case.cfg.snapshot()["rerank"]
    assert report.config["retrieval"]["fusion_method"] == "weighted_rrf"
    assert [query for query, _ in case.calls] == [QUERY, UNKNOWN_QUERY]


def test_cli_model_failure_is_reported_without_writing_eval_report(
    rerank_case, tmp_path, monkeypatch, capsys,
):
    case = rerank_case

    def fail_rerank(*args, **kwargs):
        raise RerankError("integration model is unavailable")

    monkeypatch.setattr(pipeline, "rerank", fail_rerank)
    out = tmp_path / "failed-report.json"
    for command in (
        ["ask", QUERY, "--config", str(case.config_path)],
        ["eval", "--config", str(case.config_path),
         "--qrels", str(case.qrels_path), "--out", str(out)],
    ):
        assert main(command, environ={}) == 1
        output = capsys.readouterr()
        assert "integration model is unavailable" in output.err
        assert case.target.text not in output.out
    assert not out.exists()
