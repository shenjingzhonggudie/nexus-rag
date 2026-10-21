"""rerank 的契约测试：加权排名融合 S(d) = α·S1(d) + (1−α)·S2(d)。"""

import pytest

from ragkit.retrieval.rerank import rerank
from ragkit.schemas import Chunk, ScoredChunk


def _chunk(chunk_id: str) -> Chunk:
    return Chunk(chunk_id=chunk_id, doc_id="doc", text="t", ordinal=0)


def _leg(*ids: str) -> list[ScoredChunk]:
    """按给定顺序造一条腿：列表顺序就是名次，原始分数不参与融合。"""
    return [ScoredChunk(chunk=_chunk(cid), score=1.0, stage="bm25") for cid in ids]


def test_hand_calculated_weighted_score():
    # BM25: c1(rank1) c2(rank2)；dense: c2(rank1) c1(rank2)；alpha=0.9, k=60
    # c1 = 0.9/61 + 0.1/62，c2 = 0.9/62 + 0.1/61 → c1 略高
    out = rerank([_leg("c1", "c2"), _leg("c2", "c1")], alpha=0.9, final_k=5)

    assert [r.chunk.chunk_id for r in out] == ["c1", "c2"]
    scores = {r.chunk.chunk_id: r.score for r in out}
    assert scores["c1"] == pytest.approx(0.9 / 61 + 0.1 / 62)
    assert scores["c2"] == pytest.approx(0.9 / 62 + 0.1 / 61)


def test_alpha_flips_ranking():
    # 两腿名次完全相反时，α 决定听谁的
    bm25, dense = _leg("c1", "c2"), _leg("c2", "c1")

    assert [
        r.chunk.chunk_id for r in rerank([bm25, dense], alpha=0.9, final_k=2)
    ] == ["c1", "c2"]
    assert [
        r.chunk.chunk_id for r in rerank([bm25, dense], alpha=0.1, final_k=2)
    ] == ["c2", "c1"]


def test_alpha_one_reduces_to_bm25_order():
    out = rerank([_leg("c3", "c1", "c2"), _leg("c2", "c3", "c1")], alpha=1.0, final_k=3)
    assert [r.chunk.chunk_id for r in out] == ["c3", "c1", "c2"]


def test_alpha_zero_reduces_to_dense_order():
    out = rerank([_leg("c3", "c1", "c2"), _leg("c2", "c3", "c1")], alpha=0.0, final_k=3)
    assert [r.chunk.chunk_id for r in out] == ["c2", "c3", "c1"]


def test_single_leg_ignores_alpha():
    # 单腿时权重归一化为 1，alpha 不参与（只开一路召回时不应改变排序）
    leg = _leg("c2", "c1")
    assert [r.chunk.chunk_id for r in rerank([leg], alpha=0.0, final_k=5)] == ["c2", "c1"]
    assert [r.chunk.chunk_id for r in rerank([leg], alpha=1.0, final_k=5)] == ["c2", "c1"]


def test_same_chunk_accumulates_across_legs():
    # 同一块在两腿都靠前 → 分数累加，应排第一
    out = rerank([_leg("c1", "c2"), _leg("c1", "c2")], alpha=0.5, final_k=2)
    assert out[0].chunk.chunk_id == "c1"
    assert out[0].score == pytest.approx(0.5 / 61 + 0.5 / 61)


def test_empty_legs_returns_empty():
    assert rerank([], alpha=0.9, final_k=5) == []


def test_final_k_truncates():
    out = rerank([_leg("a", "b", "c", "d")], alpha=0.9, final_k=2)
    assert len(out) == 2


def test_stage_is_rerank():
    out = rerank([_leg("a")], alpha=0.9, final_k=1)
    assert out[0].stage == "rerank"
