"""v2证据判分：严格50%边界、区间并集、必要证据与标注缺失。"""

import json
from types import SimpleNamespace

import pytest

from ragkit.config import AppConfig
from ragkit.evaluation import AnswerPoint, AnswerSection, Qrel, evaluate, load_qrels
from ragkit.evaluation.evidence import prefix_point_coverage
from ragkit.retrieval.result import RetrievalResult
from ragkit.schemas import Chunk, RetrievalTrace, ScoredChunk


def chunk(start, end, doc="a.md"):
    return Chunk(chunk_id=f"{doc}:{start}:{end}", doc_id=doc, text="证据", ordinal=0,
                 metadata={"char_start": start, "char_end": end})


def evidence(start=0, end=100, doc="a.md"):
    return AnswerSection(doc, "相关小节", start, end, "证" * (end - start))


def point(*spans):
    return AnswerPoint("具体回答要点", spans or (evidence(),))


@pytest.mark.parametrize("start,end,hit", [(99, 110, False), (0, 49, False),
                                          (0, 50, False), (0, 51, True), (0, 100, True)])
def test_strict_more_than_half_of_evidence(start, end, hit):
    hits, ratios = prefix_point_coverage([chunk(start, end)], (point(),))
    assert hits == [{0} if hit else set()]
    assert ratios[0][0] == pytest.approx(max(0, min(end, 100) - start) / 100)


def test_denominator_is_evidence_not_large_chunk():
    hits, ratios = prefix_point_coverage([chunk(0, 10000)], (point(),))
    assert hits == [{0}]
    assert ratios == [[1.0]]


def test_two_individually_insufficient_chunks_jointly_hit():
    hits, ratios = prefix_point_coverage([chunk(0, 30), chunk(30, 60)], (point(),))
    assert hits == [set(), {0}]
    assert ratios == [[0.3], [0.6]]


def test_duplicate_and_overlapping_chunks_do_not_double_count():
    hits, ratios = prefix_point_coverage([chunk(0, 40), chunk(0, 40), chunk(20, 50)], (point(),))
    assert hits == [set(), set(), set()]
    assert ratios == [[0.4], [0.4], [0.5]]


def test_gap_is_not_filled_by_bounding_interval():
    hits, ratios = prefix_point_coverage([chunk(0, 25), chunk(75, 100)], (point(),))
    assert hits[-1] == set()
    assert ratios[-1] == [0.5]


def test_different_documents_do_not_share_coordinates():
    hits, ratios = prefix_point_coverage([chunk(0, 100, "b.md")], (point(),))
    assert hits == [set()]
    assert ratios == [[0.0]]


def test_every_required_evidence_in_point_must_cross_threshold():
    p = point(evidence(), evidence(0, 100, "b.md"))
    hits, ratios = prefix_point_coverage([chunk(0, 100), chunk(0, 50, "b.md"),
                                         chunk(50, 51, "b.md")], (p,))
    assert hits == [set(), set(), {0}]
    assert ratios == [[0.0], [0.5], [0.51]]


def test_missing_offsets_do_not_create_a_hit():
    missing = Chunk(chunk_id="missing", doc_id="a.md", text="证据", ordinal=0)
    assert prefix_point_coverage([missing], (point(),)) == ([set()], [[0.0]])


def test_load_v2_preserves_points_quotes_and_flattens_evidence(tmp_path):
    path = tmp_path / "qrels.json"
    path.write_text(json.dumps([{
        "id": "q_test", "query": "具体问题", "type": "direct", "annotation_version": 2,
        "answers": [{"point": "具体答案", "evidence": [
            {"doc": "a.md", "section": "s", "start": 10, "end": 14, "quote": "具体证据"}]}],
    }], ensure_ascii=False), encoding="utf-8")
    q = load_qrels(path)[0]
    assert q.answer_points[0].point == "具体答案"
    assert q.answers == q.answer_points[0].evidence
    assert q.answers[0].quote == "具体证据"
    assert not q.is_no_answer


def test_v2_incomplete_answer_label_is_not_silently_no_answer():
    with pytest.raises(ValueError, match="必须有回答要点"):
        Qrel("问题", annotation_version=2)
    pending = Qrel("问题", annotation_version=2, annotation_status="needs_review")
    assert not pending.is_no_answer
    assert not pending.is_evaluable


def test_v2_no_answer_requires_reason_and_rejects_evidence():
    with pytest.raises(ValueError, match="缺失"):
        Qrel("问题", type="no_answer", annotation_version=2)
    with pytest.raises(ValueError, match="不能附"):
        Qrel("问题", type="no_answer", annotation_version=2,
             answer_points=(point(),), unanswerable_reason="缺失具体参数")
    q = Qrel("问题", type="no_answer", annotation_version=2,
             unanswerable_reason="缺失具体参数", annotation_status="retained_no_answer")
    assert q.is_no_answer and q.is_evaluable


def test_quote_length_and_required_support_validation():
    with pytest.raises(ValueError, match="长度"):
        AnswerSection("a", "s", 0, 10, "太短")
    with pytest.raises(ValueError, match="原文"):
        AnswerPoint("要点", (AnswerSection("a", "s", 0, 10),))


def mock_search(monkeypatch, chunks):
    import importlib
    module = importlib.import_module("ragkit.evaluation.report")
    result = RetrievalResult(
        results=[ScoredChunk(chunk=c, score=1.0, stage="bm25") for c in chunks],
        trace=RetrievalTrace(), match_score=1.0,
    )
    monkeypatch.setattr(module, "search", lambda *a, **kw: result)
    return SimpleNamespace(bm25=None, store=None, id_to_chunk={}, dim=1)


def test_evaluate_prefix_union_complete_rate_and_pending_denominators(monkeypatch):
    p1, p2 = point(), point(evidence(200, 300))
    built = mock_search(monkeypatch, [chunk(0, 60), chunk(200, 260)])
    labeled = Qrel("可回答问题", id="q_test", annotation_version=2,
                   answer_points=(p1, p2), answers=(*p1.evidence, *p2.evidence))
    pending = Qrel("待核验问题", annotation_version=2, annotation_status="needs_review")
    report = evaluate(built, AppConfig(), [labeled, pending], ks=(1, 2))
    assert report.recall_at == {1: 0.5, 2: 1.0}
    assert report.complete_at == {1: 0.0, 2: 1.0}
    assert report.n_answerable == 1 and report.n_pending == 1 and report.n_no_answer == 0
    row = report.to_dict()["per_query"][0]
    assert row["id"] == "q_test" and row["source"] == "internal"
    assert row["hits_by_prefix"] == [[0], [0, 1]]
    assert report.to_dict()["scoring"]["coverage_threshold"] == 0.5


def test_mrr_tracks_first_prefix_with_a_supported_point(monkeypatch):
    p = point()
    built = mock_search(monkeypatch, [chunk(0, 30), chunk(30, 60)])
    q = Qrel("问题", annotation_version=2, answer_points=(p,), answers=p.evidence)
    report = evaluate(built, AppConfig(), [q], ks=(1, 2))
    assert report.recall_at == {1: 0.0, 2: 1.0}
    assert report.mrr == 0.5
    assert report.per_query[0].hits_per_rank == [[], []]


def test_mixed_scoring_versions_are_rejected():
    with pytest.raises(ValueError, match="混合"):
        evaluate(None, AppConfig(), [Qrel("旧题"), Qrel("新题", annotation_version=2,
                 annotation_status="needs_review")])


def test_v2_refusal_denominators_include_retained_and_exclude_pending(monkeypatch):
    built = mock_search(monkeypatch, [])
    p = point()
    rows = [
        Qrel("已标注有答案", annotation_version=2, answer_points=(p,), answers=p.evidence),
        Qrel("保留无答案", type="no_answer", annotation_version=2,
             annotation_status="retained_no_answer", unanswerable_reason="缺少参数数值"),
        Qrel("待复核无答案", type="no_answer", annotation_version=2,
             annotation_status="needs_review", unanswerable_reason="仍待确认"),
    ]
    report = evaluate(built, AppConfig(), rows, ks=(1,))
    assert report.n_answerable == report.n_no_answer == report.n_pending == 1
    assert report.refusal_accuracy == report.false_refusal_rate == 1.0
    assert report.recall_at == report.complete_at == {1: 0.0}
