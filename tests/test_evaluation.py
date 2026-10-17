"""评测编排的契约测试：doc_id 去重、端到端跑评测集、耗时表冷/热分开。"""

from pathlib import Path

from ragkit.config import AppConfig
from ragkit.evaluation import load_qrels
from ragkit.evaluation.report import _dedup_doc_ids, evaluate
from ragkit.index import build
from ragkit.schemas import Chunk, ScoredChunk

ROOT = Path(__file__).resolve().parents[1]  # 项目根（tests/ 的上一级）


def _scored(doc_id, text="x"):
    chunk = Chunk(chunk_id=f"{doc_id}#h@0", doc_id=doc_id, text=text, ordinal=0)
    return ScoredChunk(chunk=chunk, score=1.0, stage="rerank")


def test_dedup_doc_ids_keeps_first_occurrence():
    # 同一文档的多个 chunk 都进结果 → 去重后只留一个 doc_id，顺序=首次出现
    results = [
        _scored("a.md", "a1"),
        _scored("b.md", "b1"),
        _scored("a.md", "a2"),   # a.md 的第二块，应被去重
        _scored("c.md", "c1"),
    ]

    assert _dedup_doc_ids(results) == ["a.md", "b.md", "c.md"]


def test_evaluate_end_to_end(tmp_path):
    # 用真实语料 + 真实评测集跑完整评测，验证报告结构与冷/热耗时口径
    qrels = load_qrels(ROOT / "data" / "eval" / "qrels.json")
    cfg = AppConfig(index_dir=tmp_path / "idx")
    built = build(ROOT / "data" / "raw", cfg)

    report = evaluate(built, cfg, qrels)

    assert len(report.per_query) == len(qrels)
    assert set(report.recall_at) == set(range(1, 11))
    assert 0.0 <= report.mrr <= 1.0
    for q in report.per_query:
        assert 0.0 <= q.mrr <= 1.0
        assert all(0.0 <= v <= 1.0 for v in q.recall_at.values())
        # 去重后的 retrieved 不应有重复 doc_id
        assert len(q.retrieved) == len(set(q.retrieved))
    # 耗时表：冷启动（首查）应 ≥ 热启动均值（首查含 jieba 首次加载）
    assert report.latency.cold_ms >= 0.0
    assert report.latency.warm_p95_ms >= report.latency.warm_mean_ms >= 0.0


def test_evaluate_empty_qrels_returns_zero_report(tmp_path):
    cfg = AppConfig(index_dir=tmp_path / "idx")
    built = build(ROOT / "data" / "raw", cfg)

    report = evaluate(built, cfg, [])

    assert report.per_query == []
    assert report.mrr == 0.0
    assert all(v == 0.0 for v in report.recall_at.values())
