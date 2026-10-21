"""评测编排的契约测试：区间重叠判定、端到端跑评测、拒答指标、耗时口径。"""

from pathlib import Path

import pytest

from ragkit.chunking import iter_heading_sections
from ragkit.config import AppConfig
from ragkit.evaluation import AnswerSection, Qrel, evaluate
from ragkit.evaluation.report import _hit_indices
from ragkit.index import build
from ragkit.schemas import Chunk
from ragkit.text.normalize import normalize_text


def _chunk(doc_id: str, start: int, end: int) -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}#1@1",
        doc_id=doc_id,
        text="x",
        ordinal=0,
        metadata={"char_start": start, "char_end": end},
    )


def _make_corpus(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text(
        "# 主题A\n\n## 小节1\n\n连接池能复用数据库连接，避免频繁建连的开销。\n\n"
        "## 小节2\n\n索引能加速查询，避免全表扫描。\n",
        encoding="utf-8",
    )
    return raw


def _sections(doc: str, text: str) -> list[AnswerSection]:
    """把文档的每个 ## 小节转成 AnswerSection（区间取自 normalize 后的文本）。"""
    normalized = normalize_text(text)
    return [
        AnswerSection(doc=doc, section=f"section{index}", start=start, end=end)
        for index, (start, end) in enumerate(iter_heading_sections(normalized))
    ]


def test_hit_indices_uses_interval_overlap():
    # 块 [100,300) 与答案 [200,400) 只是部分重叠 → 仍算命中。
    # 这是"不绑切分"的核心：块边界挪动不应把答案判丢。
    chunk = _chunk("a.md", 100, 300)
    answers = (AnswerSection(doc="a.md", section="s", start=200, end=400),)

    assert _hit_indices(chunk, answers) == {0}


def test_hit_indices_requires_same_doc():
    chunk = _chunk("a.md", 100, 300)
    answers = (AnswerSection(doc="b.md", section="s", start=200, end=400),)

    assert _hit_indices(chunk, answers) == set()


def test_hit_indices_without_offsets_returns_empty():
    # 没有字符偏移的块（理论上不该出现）无法判定，安全地判为未命中
    chunk = Chunk(chunk_id="a#1@1", doc_id="a.md", text="x", ordinal=0)

    assert _hit_indices(chunk, (AnswerSection("a.md", "s", 0, 10),)) == set()


def test_evaluate_end_to_end(tmp_path):
    raw = _make_corpus(tmp_path)
    cfg = AppConfig(index_dir=tmp_path / "idx")
    built = build(raw, cfg)

    text = (raw / "a.md").read_text(encoding="utf-8")
    sections = _sections("a.md", text)
    qrels = [Qrel(query="连接池复用的好处", answers=(sections[0],))]

    report = evaluate(built, cfg, qrels)

    assert len(report.per_query) == 1
    assert report.n_no_answer == 0
    assert report.recall_at[1] == pytest.approx(1.0)   # 首个块即命中第 1 小节
    assert report.mrr == pytest.approx(1.0)
    assert report.latency.cold_ms >= 0.0
    assert report.latency.warm_p95_ms >= 0.0


def test_evaluate_refusal_metrics(tmp_path):
    # 无答案 query 与有答案 query 各一条：验证拒答准确率、误拒率，
    # 以及 recall 只统计有答案 query（不被无答案的 0 分稀释）
    raw = _make_corpus(tmp_path)
    cfg = AppConfig(index_dir=tmp_path / "idx")  # 默认 refuse_threshold=0.5
    built = build(raw, cfg)

    text = (raw / "a.md").read_text(encoding="utf-8")
    sections = _sections("a.md", text)
    qrels = [
        Qrel(query="连接池复用的好处", answers=(sections[0],)),
        Qrel(query="XYZ 的 QQQ 是什么", type="no_answer"),  # 语料里无答案
    ]

    report = evaluate(built, cfg, qrels)

    assert report.n_no_answer == 1
    assert report.refusal_accuracy == 1.0       # 无答案 query 被正确拒答
    assert report.false_refusal_rate == 0.0     # 有答案 query 没被误拒
    # recall 只在有答案 query 上平均；若无答案参与会被稀释成 0.5
    assert report.recall_at[1] == pytest.approx(1.0)


def test_report_to_dict_includes_refusal_and_type():
    from ragkit.evaluation.report import EvalReport, LatencyStats

    report = EvalReport(
        recall_at={1: 0.5},
        mrr=0.5,
        per_query=[],
        latency=LatencyStats(0.0, 0.0, 0.0, 0.0),
        refusal_accuracy=0.75,
        false_refusal_rate=0.1,
        n_no_answer=4,
    )

    data = report.to_dict()

    assert data["refusal"] == {"accuracy": 0.75, "false_rate": 0.1, "n_no_answer": 4}


def test_evaluate_empty_qrels_returns_zero_report(tmp_path):
    raw = _make_corpus(tmp_path)
    cfg = AppConfig(index_dir=tmp_path / "idx")
    built = build(raw, cfg)

    report = evaluate(built, cfg, [])

    assert report.per_query == []
    assert report.mrr == 0.0
    assert all(v == 0.0 for v in report.recall_at.values())
