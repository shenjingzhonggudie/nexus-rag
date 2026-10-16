"""rerank 的契约测试：手算样例、final_k 截断、stage、sub_scores、边界、确定性。"""

import importlib

import numpy as np
import pytest

from ragkit.retrieval.rerank import rerank
from ragkit.schemas import Chunk, ScoredChunk
from ragkit.stores import VectorStore


def _chunk(chunk_id: str, text: str = "t") -> Chunk:
    return Chunk(chunk_id=chunk_id, doc_id="doc", text=text, ordinal=0)


def _patch_embed(monkeypatch, vec):
    # 用 importlib 拿真实模块对象再 patch：`ragkit/retrieval/__init__.py` 里
    # `from ...rerank import rerank` 让函数名与子模块名同名，遮蔽了
    # `ragkit.retrieval.rerank` 子模块属性，字符串路径会解析成函数而失败。
    rerank_mod = importlib.import_module("ragkit.retrieval.rerank")
    monkeypatch.setattr(rerank_mod, "embed_text", lambda text, *, dim: list(vec))


def test_hand_calculated_ranking(monkeypatch):
    # q=[0.6,0.8,0,0]；store 各行 a=[1,0,0,0] b=[0,1,0,0] c=[0,0,1,0]
    # 手算：a=0.6 b=0.8 c=0 → 降序 b>a>c，final_k=2 → [b, a]
    _patch_embed(monkeypatch, [0.6, 0.8, 0.0, 0.0])
    store = VectorStore(
        ids=["a", "b", "c"],
        matrix=np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]], dtype=np.float32),
        metadata=[{}, {}, {}],
    )
    a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
    cands = [
        ScoredChunk(chunk=c, score=1.0, stage="rrf"),
        ScoredChunk(chunk=a, score=0.9, stage="rrf"),
        ScoredChunk(chunk=b, score=0.8, stage="rrf"),
    ]

    out = rerank(cands, "q", store, dim=4, final_k=2)

    assert [r.chunk.chunk_id for r in out] == ["b", "a"]
    assert [r.score for r in out] == pytest.approx([0.8, 0.6])


def test_final_k_truncates(monkeypatch):
    _patch_embed(monkeypatch, [1.0, 0.0, 0.0, 0.0])
    store = VectorStore(
        ids=["a", "b", "c"],
        matrix=np.array([[1, 0, 0, 0], [1, 0, 0, 0], [1, 0, 0, 0]], dtype=np.float32),
        metadata=[{}, {}, {}],
    )
    cands = [ScoredChunk(chunk=_chunk(i), score=1.0, stage="rrf") for i in ("a", "b", "c")]

    assert len(rerank(cands, "q", store, dim=4, final_k=2)) == 2


def test_stage_is_rerank(monkeypatch):
    _patch_embed(monkeypatch, [1.0, 0.0, 0.0, 0.0])
    store = VectorStore(
        ids=["a"], matrix=np.array([[1, 0, 0, 0]], dtype=np.float32), metadata=[{}]
    )
    out = rerank([ScoredChunk(chunk=_chunk("a"), score=0.9, stage="rrf")], "q", store, dim=4, final_k=1)

    assert all(r.stage == "rerank" for r in out)


def test_score_is_python_float(monkeypatch):
    _patch_embed(monkeypatch, [1.0, 0.0, 0.0, 0.0])
    store = VectorStore(
        ids=["a"], matrix=np.array([[1, 0, 0, 0]], dtype=np.float32), metadata=[{}]
    )
    out = rerank([ScoredChunk(chunk=_chunk("a"), score=0.9, stage="rrf")], "q", store, dim=4, final_k=1)

    assert isinstance(out[0].score, float)
    assert not isinstance(out[0].score, np.floating)


def test_sub_scores_preserves_prev(monkeypatch):
    # 精排前分数记入 sub_scores["prev"]，原有 sub_scores 保留
    _patch_embed(monkeypatch, [1.0, 0.0, 0.0, 0.0])
    store = VectorStore(
        ids=["a"], matrix=np.array([[1, 0, 0, 0]], dtype=np.float32), metadata=[{}]
    )
    a = _chunk("a")
    out = rerank(
        [ScoredChunk(chunk=a, score=0.9, stage="rrf", sub_scores={"bm25": 5.0})],
        "q",
        store,
        dim=4,
        final_k=1,
    )

    assert out[0].sub_scores["prev"] == pytest.approx(0.9)
    assert out[0].sub_scores["bm25"] == pytest.approx(5.0)


def test_empty_candidates_returns_empty(monkeypatch):
    _patch_embed(monkeypatch, [1.0, 0.0, 0.0, 0.0])
    store = VectorStore(
        ids=["a"], matrix=np.array([[1, 0, 0, 0]], dtype=np.float32), metadata=[{}]
    )

    assert rerank([], "q", store, dim=4, final_k=2) == []


def test_candidate_not_in_store_is_dropped(monkeypatch):
    # chunk_id 不在 store 里的候选无法打分，被丢弃
    _patch_embed(monkeypatch, [1.0, 0.0, 0.0, 0.0])
    store = VectorStore(
        ids=["a"], matrix=np.array([[1, 0, 0, 0]], dtype=np.float32), metadata=[{}]
    )
    a = _chunk("a")
    ghost = _chunk("ghost")
    cands = [
        ScoredChunk(chunk=ghost, score=1.0, stage="rrf"),
        ScoredChunk(chunk=a, score=0.5, stage="rrf"),
    ]

    out = rerank(cands, "q", store, dim=4, final_k=2)

    assert [r.chunk.chunk_id for r in out] == ["a"]


def test_deterministic(monkeypatch):
    _patch_embed(monkeypatch, [0.6, 0.8, 0.0, 0.0])
    store = VectorStore(
        ids=["a", "b", "c"],
        matrix=np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]], dtype=np.float32),
        metadata=[{}, {}, {}],
    )
    cands = [ScoredChunk(chunk=_chunk(i), score=1.0, stage="rrf") for i in ("a", "b", "c")]

    first = [(r.chunk.chunk_id, r.score) for r in rerank(cands, "q", store, dim=4, final_k=3)]
    second = [(r.chunk.chunk_id, r.score) for r in rerank(cands, "q", store, dim=4, final_k=3)]

    assert first == second
