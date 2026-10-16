"""RRF 融合的契约测试：按 chunk_id 聚合累加、去重、单腿退化、空腿容错、top_k。"""

import pytest

from ragkit.retrieval.fusion import rrf_fuse
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
