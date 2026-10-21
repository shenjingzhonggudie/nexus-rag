"""评测编排的契约测试：chunk_id 提取、端到端跑评测集、耗时表冷/热分开。"""

from pathlib import Path

from ragkit.config import AppConfig
from ragkit.evaluation import Qrel, evaluate
from ragkit.evaluation.report import _extract_chunk_ids
from ragkit.index import build
from ragkit.schemas import Chunk, ScoredChunk


def _scored(chunk_id: str) -> ScoredChunk:
    chunk = Chunk(chunk_id=chunk_id, doc_id="doc", text="x", ordinal=0)
    return ScoredChunk(chunk=chunk, score=1.0, stage="rrf")


def _make_corpus(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text(
        "# 主题A\n\n## 小节1\n\n这是小节1的内容，讲第一个知识点。\n\n"
        "## 小节2\n\n这是小节2的内容，讲第二个知识点。\n",
        encoding="utf-8",
    )
    return raw


def test_extract_chunk_ids():
    # 块级评测：直接提取 chunk_id（融合已按 chunk_id 去重，无需再按 doc_id 去重）
    results = [_scored("a.md#h1@1"), _scored("b.md#h2@1"), _scored("c.md#h3@1")]

    assert _extract_chunk_ids(results) == ["a.md#h1@1", "b.md#h2@1", "c.md#h3@1"]


def test_evaluate_end_to_end(tmp_path):
    # 用自包含临时语料跑完整评测，验证块级 recall 对齐与冷/热耗时口径
    raw = _make_corpus(tmp_path)
    cfg = AppConfig(index_dir=tmp_path / "idx")
    built = build(raw, cfg)

    # 用 built 的第一块作为答案，构造块级 qrels（验证 chunk_id 对齐）
    answer_chunk = built.store.ids[0]
    qrels = [Qrel(query="讲第一个知识点的内容", relevant=frozenset([answer_chunk]))]

    report = evaluate(built, cfg, qrels)

    assert len(report.per_query) == len(qrels)
    assert set(report.recall_at) == set(range(1, 11))
    assert 0.0 <= report.mrr <= 1.0
    for q in report.per_query:
        assert 0.0 <= q.mrr <= 1.0
        assert all(0.0 <= v <= 1.0 for v in q.recall_at.values())
    assert report.latency.cold_ms >= 0.0
    assert report.latency.warm_p95_ms >= report.latency.warm_mean_ms >= 0.0


def test_evaluate_empty_qrels_returns_zero_report(tmp_path):
    raw = _make_corpus(tmp_path)
    cfg = AppConfig(index_dir=tmp_path / "idx")
    built = build(raw, cfg)

    report = evaluate(built, cfg, [])

    assert report.per_query == []
    assert report.mrr == 0.0
    assert all(v == 0.0 for v in report.recall_at.values())
