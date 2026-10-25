"""等权与加权 RRF 融合的契约测试：名次计分、权重、去重和候选上限。"""

import pytest

from ragkit.retrieval.fusion import rrf_fuse, weighted_rrf_fuse
from ragkit.schemas import Chunk, ScoredChunk


def _chunk(chunk_id: str, text: str = "t") -> Chunk:
    return Chunk(chunk_id=chunk_id, doc_id="doc", text=text, ordinal=0)


def _scored(chunk: Chunk, score: float, stage: str = "bm25") -> ScoredChunk:
    return ScoredChunk(chunk=chunk, score=score, stage=stage)


def test_same_chunk_across_legs_accumulates():
    c1 = _chunk("c1")
    c2 = _chunk("c2")
    bm25 = [_scored(c1, 9.0), _scored(c2, 8.0)]
    dense = [_scored(c1, 0.9, "dense")]

    out = rrf_fuse([bm25, dense])

    # c1 出现在两条腿：1/61 (bm25 rank1) + 1/61 (dense rank1)
    # c2 只在 bm25：1/62 (bm25 rank2) → c1 排前
    assert [r.chunk.chunk_id for r in out] == ["c1", "c2"]
    c1_score = next(r.score for r in out if r.chunk.chunk_id == "c1")
    assert c1_score == pytest.approx(1 / 61 + 1 / 61)


def test_no_duplicate_chunk_in_output():
    # naive concat 会让同一块出现两次；按 chunk_id 聚合后只应出现一次
    c1 = _chunk("c1")
    out = rrf_fuse([[_scored(c1, 9.0)], [_scored(c1, 0.9, "dense")]])

    ids = [r.chunk.chunk_id for r in out]
    assert ids == ["c1"]
    assert len(ids) == 1


def test_preserves_chunk_object():
    # 修复过的 bug：输出 chunk 字段必须是 Chunk 对象，不是 chunk_id 字符串
    c1 = _chunk("c1")
    out = rrf_fuse([[_scored(c1, 9.0)]])

    assert out[0].chunk is c1


def test_stage_is_rrf():
    c1 = _chunk("c1")
    out = rrf_fuse([[_scored(c1, 9.0)]])

    assert all(r.stage == "rrf" for r in out)


def test_single_leg_degenerates():
    # 消融：只传一条腿时退化为该腿的 rank 顺序
    c1 = _chunk("c1")
    c2 = _chunk("c2")
    bm25 = [_scored(c1, 9.0), _scored(c2, 8.0)]

    out = rrf_fuse([bm25])

    assert [r.chunk.chunk_id for r in out] == ["c1", "c2"]
    assert [r.score for r in out] == pytest.approx([1 / 61, 1 / 62])


def test_empty_leg_is_ignored():
    c1 = _chunk("c1")
    out = rrf_fuse([[_scored(c1, 9.0)], []])

    assert [r.chunk.chunk_id for r in out] == ["c1"]


def test_all_empty_returns_empty():
    assert rrf_fuse([[], []]) == []
    assert rrf_fuse([]) == []


def test_top_k_limits():
    chunks = [_chunk(f"c{i}") for i in range(5)]
    leg = [_scored(c, 1.0) for c in chunks]

    assert len(rrf_fuse([leg], top_k=3)) == 3


def test_k_constant_affects_score():
    c1 = _chunk("c1")

    # k=0 时第一名的 RRF 分 = 1/(0+1) = 1.0
    out = rrf_fuse([[_scored(c1, 9.0)]], k=0)

    assert out[0].score == pytest.approx(1.0)


def _leg(*ids: str) -> list[ScoredChunk]:
    """按给定顺序造一条腿：列表顺序就是名次，原始分数不参与融合。"""
    return [_scored(_chunk(cid), 1.0) for cid in ids]


def test_hand_calculated_weighted_score():
    # BM25: c1(rank1) c2(rank2)；dense: c2(rank1) c1(rank2)；alpha=0.9, k=60
    # c1 = 0.9/61 + 0.1/62，c2 = 0.9/62 + 0.1/61 → c1 略高
    out = weighted_rrf_fuse([_leg("c1", "c2"), _leg("c2", "c1")], alpha=0.9, top_k=5)

    assert [r.chunk.chunk_id for r in out] == ["c1", "c2"]
    scores = {r.chunk.chunk_id: r.score for r in out}
    assert scores["c1"] == pytest.approx(0.9 / 61 + 0.1 / 62)
    assert scores["c2"] == pytest.approx(0.9 / 62 + 0.1 / 61)


def test_alpha_flips_ranking():
    bm25, dense = _leg("c1", "c2"), _leg("c2", "c1")

    assert [
        r.chunk.chunk_id for r in weighted_rrf_fuse([bm25, dense], alpha=0.9, top_k=2)
    ] == ["c1", "c2"]
    assert [
        r.chunk.chunk_id for r in weighted_rrf_fuse([bm25, dense], alpha=0.1, top_k=2)
    ] == ["c2", "c1"]


def test_alpha_one_reduces_to_bm25_order():
    out = weighted_rrf_fuse(
        [_leg("c3", "c1", "c2"), _leg("c2", "c3", "c1")], alpha=1.0, top_k=3
    )
    assert [r.chunk.chunk_id for r in out] == ["c3", "c1", "c2"]


def test_alpha_zero_reduces_to_dense_order():
    out = weighted_rrf_fuse(
        [_leg("c3", "c1", "c2"), _leg("c2", "c3", "c1")], alpha=0.0, top_k=3
    )
    assert [r.chunk.chunk_id for r in out] == ["c2", "c3", "c1"]


def test_single_leg_ignores_alpha():
    leg = _leg("c2", "c1")
    assert [r.chunk.chunk_id for r in weighted_rrf_fuse([leg], alpha=0.0, top_k=5)] == ["c2", "c1"]
    assert [r.chunk.chunk_id for r in weighted_rrf_fuse([leg], alpha=1.0, top_k=5)] == ["c2", "c1"]


def test_weighted_same_chunk_accumulates_across_legs():
    out = weighted_rrf_fuse([_leg("c1", "c2"), _leg("c1", "c2")], alpha=0.5, top_k=2)
    assert out[0].chunk.chunk_id == "c1"
    assert out[0].score == pytest.approx(0.5 / 61 + 0.5 / 61)


def test_weighted_empty_legs_returns_empty():
    assert weighted_rrf_fuse([], alpha=0.9, top_k=5) == []
    assert weighted_rrf_fuse([[], []], alpha=0.9, top_k=5) == []


def test_weighted_top_k_truncates():
    out = weighted_rrf_fuse([_leg("a", "b", "c", "d")], alpha=0.9, top_k=2)
    assert len(out) == 2


def test_stage_is_weighted_rrf():
    out = weighted_rrf_fuse([_leg("a")], alpha=0.9, top_k=1)
    assert out[0].stage == "weighted_rrf"


def test_more_than_two_legs_use_equal_weights():
    out = weighted_rrf_fuse([_leg("a"), _leg("b"), _leg("c")], alpha=1.0)

    assert [r.chunk.chunk_id for r in out] == ["a", "b", "c"]
    assert [r.score for r in out] == pytest.approx([1 / (3 * 61)] * 3)


def test_weighted_ties_preserve_first_seen_order_and_chunk():
    first = _chunk("a", "first copy")
    duplicate = _chunk("a", "later copy")
    out = weighted_rrf_fuse(
        [[_scored(first, -99.0), _scored(_chunk("b"), 100.0)],
         [_scored(_chunk("b"), -99.0), _scored(duplicate, 100.0)]],
        alpha=0.5,
    )

    assert [r.chunk.chunk_id for r in out] == ["a", "b"]
    assert out[0].chunk is first
    assert out[0].score == pytest.approx(out[1].score)


def test_zero_weight_leg_candidates_remain_with_zero_score():
    out = weighted_rrf_fuse([_leg("a"), _leg("b")], alpha=1.0)

    assert [r.chunk.chunk_id for r in out] == ["a", "b"]
    assert out[1].score == 0.0
