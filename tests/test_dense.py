"""dense 检索的契约测试：点积排序、stage、top_k、边界（空 query / 空 store）、可复现。"""

import numpy as np
import pytest

from ragkit.retrieval.dense import dense_search
from ragkit.schemas import Chunk
from ragkit.stores import VectorStore


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(chunk_id=chunk_id, doc_id="doc", text=text, ordinal=0)


def _store(ids, matrix, dim=4) -> VectorStore:
    return VectorStore(
        ids=ids,
        matrix=np.array(matrix, dtype=np.float32),
        metadata=[{} for _ in ids],
    )


def _patch_embed(monkeypatch, vec_map):
    """用固定向量表替换 embed_text，摆脱 jieba，让分数可手算。"""
    monkeypatch.setattr(
        "ragkit.retrieval.dense.embed_text",
        lambda text, *, dim: list(vec_map[text]),
    )


def test_returns_sorted_by_cosine(monkeypatch):
    _patch_embed(monkeypatch, {"q": [0.2, 0.5, 0.3, 0.0]})
    store = _store(["c1", "c2", "c3"], [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]])
    chunks = {"c1": _chunk("c1", "a"), "c2": _chunk("c2", "b"), "c3": _chunk("c3", "c")}

    top = dense_search("q", store, chunks, dim=4, top_k=10)

    # 点积：c1=0.2, c2=0.5, c3=0.3 → 降序 c2 > c3 > c1
    assert [r.chunk.chunk_id for r in top] == ["c2", "c3", "c1"]
    assert [r.score for r in top] == pytest.approx([0.5, 0.3, 0.2])


def test_score_is_python_float(monkeypatch):
    # 契约：score 必须是纯 Python float，不是 numpy 标量
    _patch_embed(monkeypatch, {"q": [1.0, 0.0, 0.0, 0.0]})
    store = _store(["c1"], [[1, 0, 0, 0]])
    chunks = {"c1": _chunk("c1", "a")}

    score = dense_search("q", store, chunks, dim=4)[0].score

    assert isinstance(score, float)
    assert not isinstance(score, np.floating)


def test_stage_is_dense(monkeypatch):
    _patch_embed(monkeypatch, {"q": [1.0, 0.0, 0.0, 0.0]})
    store = _store(["c1", "c2"], [[1, 0, 0, 0], [0, 1, 0, 0]])
    chunks = {"c1": _chunk("c1", "a"), "c2": _chunk("c2", "b")}

    top = dense_search("q", store, chunks, dim=4)

    assert all(r.stage == "dense" for r in top)


def test_top_k_limits(monkeypatch):
    _patch_embed(monkeypatch, {"q": [1.0, 0.0, 0.0, 0.0]})
    store = _store(["c1", "c2", "c3"], [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]])
    chunks = {"c1": _chunk("c1", "a"), "c2": _chunk("c2", "b"), "c3": _chunk("c3", "c")}

    assert len(dense_search("q", store, chunks, dim=4, top_k=2)) == 2


def test_identical_text_scores_one():
    # 真实 embed_text：向量已归一化，query 与某块同文本时点积=余弦=1
    from ragkit.embeddings import embed_text

    v = embed_text("容器冷启动", dim=8)
    store = VectorStore(ids=["c1"], matrix=np.array([v], dtype=np.float32), metadata=[{}])
    chunks = {"c1": _chunk("c1", "容器冷启动")}

    top = dense_search("容器冷启动", store, chunks, dim=8)

    assert top[0].score == pytest.approx(1.0, abs=1e-5)


def test_empty_query_returns_zero_score_chunks(monkeypatch):
    # 空 query 与 BM25 对齐：返回 top_k 个分数全 0 的块
    _patch_embed(monkeypatch, {"": [0.0, 0.0, 0.0, 0.0]})
    store = _store(["c1", "c2"], [[1, 0, 0, 0], [0, 1, 0, 0]])
    chunks = {"c1": _chunk("c1", "a"), "c2": _chunk("c2", "b")}

    top = dense_search("", store, chunks, dim=4)

    assert len(top) == 2
    assert all(r.score == 0.0 for r in top)


def test_empty_store_returns_empty(monkeypatch):
    _patch_embed(monkeypatch, {"q": [1.0, 0.0, 0.0, 0.0]})
    store = VectorStore(ids=[], matrix=np.zeros((0, 4), dtype=np.float32), metadata=[])

    assert dense_search("q", store, {}, dim=4) == []


def test_deterministic(monkeypatch):
    _patch_embed(monkeypatch, {"q": [0.2, 0.5, 0.3, 0.0]})
    store = _store(["c1", "c2", "c3"], [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]])
    chunks = {"c1": _chunk("c1", "a"), "c2": _chunk("c2", "b"), "c3": _chunk("c3", "c")}

    first = [(r.chunk.chunk_id, r.score) for r in dense_search("q", store, chunks, dim=4)]
    second = [(r.chunk.chunk_id, r.score) for r in dense_search("q", store, chunks, dim=4)]

    assert first == second
