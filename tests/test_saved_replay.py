"""保存结果重评分只使用合成标注、块和保存行，不读取任何系统报告。"""

import json
from copy import deepcopy

import pytest

from ragkit.evaluation.qrels import AnswerPoint, AnswerSection, Qrel
from ragkit.evaluation.replay import rescore_saved_results
from ragkit.schemas import Chunk


def point(start=0, end=100, doc="a.md", label="必要要点"):
    return AnswerPoint(label, (AnswerSection(doc, "证据小节", start, end, "证" * (end - start)),))


def answerable(query="问题", *, points=None, status="complete"):
    points = (point(),) if points is None else points
    return Qrel(query, id=f"id:{query}", annotation_version=2, answer_points=points,
                answers=tuple(e for p in points for e in p.evidence), annotation_status=status)


def no_answer(query="无答案", *, status="complete"):
    return Qrel(query, id=f"id:{query}", type="no_answer", annotation_version=2,
                annotation_status=status, unanswerable_reason="给定原文缺少所问数值")


def chunk(chunk_id="c", start=0, end=100, doc="a.md"):
    return Chunk(chunk_id, doc, "文" * (end - start), 0,
                 metadata={"char_start": start, "char_end": end})


def saved(query="问题", retrieved=("c",), refused=False, **old_fields):
    return {"query": query, "retrieved": list(retrieved), "refused": refused, **old_fields}


def test_ignores_old_hits_scores_and_labels_and_does_not_mutate_inputs():
    qrels = [answerable(), no_answer()]
    rows = [saved(hits_per_rank=[[0]], hits_by_prefix=[[0]], recall_at={1: 1.0},
                  recall=1.0, mrr=1.0, complete_at={1: 1.0},
                  type="no_answer", is_no_answer=True),
            saved("无答案", (), True, type="direct", is_no_answer=False, mrr=999)]
    chunks = {"c": chunk(doc="wrong.md")}
    before = deepcopy((qrels, rows, chunks))
    report = rescore_saved_results(qrels, rows, chunks, ks=(1,))
    assert report["recall_at"] == report["complete_at"] == {1: 0.0}
    assert report["mrr"] == 0.0
    assert report["n_answerable"] == report["n_no_answer"] == 1
    assert not report["per_query"][0]["is_no_answer"]
    assert report["per_query"][1]["is_no_answer"]
    assert report["refusal"]["correct"] == report["refusal"]["total"] == 1
    assert (qrels, rows, chunks) == before
    report["per_query"][0]["retrieved"].append("changed")
    assert rows[0]["retrieved"] == ["c"]
    json.dumps(report, ensure_ascii=False)


@pytest.mark.parametrize("end, expected", [(50, 0.0), (51, 1.0)])
def test_strict_50_and_51_percent(end, expected):
    report = rescore_saved_results([answerable()], [saved()], {"c": chunk(end=end)}, ks=(1,))
    assert report["recall_at"] == report["complete_at"] == {1: expected}
    assert report["mrr"] == expected
    assert report["per_query"][0]["point_coverage_by_prefix"] == [[end / 100]]


def test_prefix_union_creates_first_hit_at_rank_two_and_large_k_saturates():
    report = rescore_saved_results([answerable()], [saved(retrieved=("left", "right"))],
                                  {"left": chunk("left", 0, 30),
                                   "right": chunk("right", 30, 60)}, ks=(1, 2, 5))
    assert report["recall_at"] == report["complete_at"] == {1: 0.0, 2: 1.0, 5: 1.0}
    assert report["mrr"] == 0.5
    assert report["per_query"][0]["hits_by_prefix"] == [[], [0]]
    assert report["per_query"][0]["point_coverage_by_prefix"] == [[0.3], [0.6]]


def test_overlap_duplicates_gaps_and_other_documents_do_not_inflate_union():
    chunks = {"left": chunk("left", 0, 25), "right": chunk("right", 75, 100),
              "overlap": chunk("overlap", 5, 20), "other": chunk("other", doc="b.md")}
    retrieved = ("left", "left", "overlap", "right", "other")
    report = rescore_saved_results([answerable()], [saved(retrieved=retrieved)], chunks)
    row = report["per_query"][0]
    assert row["retrieved"] == list(retrieved)
    assert row["hits_by_prefix"] == [[]] * 5
    assert row["point_coverage_by_prefix"] == [[0.25], [0.25], [0.25], [0.5], [0.5]]
    assert report["mrr"] == 0.0


def test_every_required_support_must_cross_threshold_and_denominator_is_evidence():
    p = AnswerPoint("跨文档的必要条件", (point().evidence[0], point(doc="b.md").evidence[0]))
    chunks = {"a": chunk("a", 0, 10000), "b": chunk("b", 0, 50, "b.md"),
              "tail": chunk("tail", 50, 51, "b.md")}
    report = rescore_saved_results([answerable(points=(p,))],
                                  [saved(retrieved=("a", "b", "tail"))], chunks, ks=(1, 2, 3))
    assert report["recall_at"] == {1: 0.0, 2: 0.0, 3: 1.0}
    assert report["mrr"] == pytest.approx(1 / 3)
    assert report["per_query"][0]["point_coverage_by_prefix"] == [[0.0], [0.5], [0.51]]


def test_pending_known_points_and_no_answer_refusals_use_separate_denominators():
    qrels = [answerable(points=(point(label="p1"), point(200, 300, label="p2"))),
             answerable("待复核", status="needs_review"),
             no_answer("待复核无答案", status="needs_review"),
             no_answer(status="retained_no_answer"), no_answer("未拒答的无答案")]
    rows = [saved(retrieved=("c", "later"), refused=True),
            saved("待复核", refused=True), saved("待复核无答案", (), True),
            saved("无答案", (), True), saved("未拒答的无答案", (), False)]
    report = rescore_saved_results(qrels, rows, {"c": chunk(),
                                              "later": chunk("later", 200, 300)}, ks=(1, 2))
    assert (report["n_queries"], report["n_answerable"], report["n_no_answer"],
            report["n_pending"]) == (5, 1, 2, 2)
    assert report["recall_at"] == {1: 0.5, 2: 1.0}
    assert report["complete_at"] == {1: 0.0, 2: 1.0}
    assert report["mrr"] == 1.0
    assert report["refusal"] == {"correct": 1, "total": 2, "accuracy": 0.5,
                                 "false_refusals": 1, "answerable_total": 1, "false_rate": 1.0}
    assert report["conservative_complete"] == {
        "denominator": 3, "complete_at": {1: 0.0, 2: pytest.approx(1 / 3)}}
    pending = report["per_query"][1]
    assert not pending["evaluated"] and pending["annotation_status"] == "needs_review"
    assert pending["recall_at"] == {1: 1.0, 2: 1.0} and pending["mrr"] == 1.0
    assert pending["complete_at"] == {1: 0.0, 2: 0.0}
    assert pending["point_labels"] == ["必要要点"]


def test_macro_average_weights_queries_equally_not_by_number_of_points():
    qrels = [answerable(points=(point(), point(200, 300))), answerable("第二题")]
    report = rescore_saved_results(qrels, [saved(), saved("第二题")], {"c": chunk()}, ks=(1,))
    assert report["recall_at"] == {1: 0.75}
    assert report["complete_at"] == {1: 0.5}


def test_exact_query_matching_allows_different_whitespace_and_qrel_order():
    qrels = [answerable(" 问题"), answerable()]
    rows = [saved(retrieved=()), saved(" 问题")]
    report = rescore_saved_results(qrels, rows, {"c": chunk()}, ks=(1,))
    assert [r["query"] for r in report["per_query"]] == [" 问题", "问题"]
    assert [r["recall_at"][1] for r in report["per_query"]] == [1.0, 0.0]


@pytest.mark.parametrize("qrels, rows, expected_pending", [
    ([], [], 0),
    ([answerable(points=(), status="needs_review")], [saved(retrieved=())], 1),
    ([no_answer()], [saved("无答案", (), False)], 0),
])
def test_empty_metric_denominators_are_explicit_zeros(qrels, rows, expected_pending):
    report = rescore_saved_results(qrels, rows, {}, ks=(1,))
    assert report["n_answerable"] == 0 and report["n_pending"] == expected_pending
    assert report["recall_at"] == report["complete_at"] == {1: 0.0}
    assert report["mrr"] == 0.0
    assert report["conservative_complete"] == {
        "denominator": expected_pending, "complete_at": {1: 0.0}}
    assert "latency" not in report
    assert report["scoring"]["mode"] == "saved_retrieval_evidence_regrade"
    assert report["scoring"]["threshold"] == 0.5
    assert report["scoring"]["comparison"] == ">"
    assert report["scoring"]["denominator"] == "evidence_characters"
    assert report["scoring"]["latency_measured"] is False
    assert report["scoring"]["answer_text_verified"] is False


@pytest.mark.parametrize("qrels, rows, error", [
    ([answerable(), answerable()], [saved()], "duplicate qrel query"),
    ([answerable()], [saved(), saved()], "duplicate saved query"),
    ([answerable()], [], "missing queries"),
    ([answerable()], [saved(), saved("额外题", ())], "extra queries"),
    ([answerable()], [saved(" 问题", ())], "match qrels exactly"),
    ([Qrel("旧题")], [saved("旧题", ())], "v2"),
    ([answerable(), Qrel("旧题")], [saved(), saved("旧题", ())], "mixed/non-v2"),
])
def test_rejects_query_mismatch_duplicates_and_non_v2(qrels, rows, error):
    with pytest.raises(ValueError, match=error):
        rescore_saved_results(qrels, rows, {"c": chunk()})


@pytest.mark.parametrize("field", ["query", "retrieved", "refused"])
def test_missing_required_saved_fields_are_errors(field):
    row = saved()
    del row[field]
    with pytest.raises(ValueError, match=field):
        rescore_saved_results([answerable()], [row], {"c": chunk()})


@pytest.mark.parametrize("refused", [None, 0, 1, "false", [], {}])
def test_refused_must_be_bool(refused):
    with pytest.raises(ValueError, match="refused must be bool"):
        rescore_saved_results([answerable()], [saved(refused=refused)], {"c": chunk()})


def test_unknown_chunk_is_an_error_even_for_pending_or_no_answer():
    for qrel in [answerable(), answerable(status="needs_review"), no_answer("问题")]:
        with pytest.raises(ValueError, match="unknown chunk ID"):
            rescore_saved_results([qrel], [saved(retrieved=("missing",))], {})


@pytest.mark.parametrize("metadata", [
    {}, {"char_start": 0}, {"char_end": 100}, None,
    {"char_start": None, "char_end": 100},
    {"char_start": "0", "char_end": 100},
    {"char_start": 0.0, "char_end": 100},
    {"char_start": False, "char_end": 100},
    {"char_start": 0, "char_end": True},
    {"char_start": 0, "char_end": "100"},
    {"char_start": -1, "char_end": 100},
    {"char_start": 100, "char_end": 100},
    {"char_start": 101, "char_end": 100},
])
def test_missing_or_illegal_chunk_offsets_are_errors(metadata):
    bad = chunk()
    bad.metadata = metadata
    with pytest.raises(ValueError, match="offsets"):
        rescore_saved_results([answerable()], [saved()], {"c": bad})


@pytest.mark.parametrize("retrieved", [None, "c", ("c",), [1], [None], [""]])
def test_invalid_retrieved_shape_is_an_error(retrieved):
    row = saved()
    row["retrieved"] = retrieved
    with pytest.raises(ValueError, match="retrieved"):
        rescore_saved_results([answerable()], [row], {"c": chunk()})


@pytest.mark.parametrize("ks", [(), (0,), (-1,), (True,), (1.0,), (1, 1), None])
def test_invalid_cutoffs_are_errors(ks):
    with pytest.raises(ValueError, match="positive integers"):
        rescore_saved_results([answerable()], [saved()], {"c": chunk()}, ks=ks)


@pytest.mark.parametrize("start,end", [(0.0, 100.0), (False, 100), (True, 101)])
def test_evidence_offsets_must_also_be_real_integers(start, end):
    e = AnswerSection("a.md", "s", start, end, "证" * int(end - start))
    q = answerable(points=(AnswerPoint("必要要点", (e,)),))
    with pytest.raises(ValueError, match="evidence offsets"):
        rescore_saved_results([q], [saved()], {"c": chunk()})
