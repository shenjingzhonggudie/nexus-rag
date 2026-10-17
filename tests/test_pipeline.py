"""检索流水线的契约测试：开关组合、trace 阶段与候选数口径、返回类型。"""

import numpy as np
import pytest

from ragkit.config import RetrievalConfig
from ragkit.embeddings import embed_text
from ragkit.retrieval.bm25 import BM25Index
from ragkit.retrieval.pipeline import search
from ragkit.retrieval.result import RetrievalResult
from ragkit.schemas import Chunk
from ragkit.stores import VectorStore

DIM = 8


def _fixture():
    texts = ["容器冷启动优化", "数据库连接池配置", "缓存击穿与雪崩"]
    chunks = [
        Chunk(chunk_id=f"c{i}", doc_id="doc", text=t, ordinal=i)
        for i, t in enumerate(texts)
    ]
    id_to_chunk = {c.chunk_id: c for c in chunks}
    bm25 = BM25Index(chunks)
    store = VectorStore(
        ids=[c.chunk_id for c in chunks],
        matrix=np.array([embed_text(c.text, dim=DIM) for c in chunks], dtype=np.float32),
        metadata=[{} for _ in chunks],
    )
    return bm25, store, id_to_chunk


def _search(query, bm25, store, id_to_chunk, **cfg):
    return search(
        query,
        bm25=bm25,
        store=store,
        id_to_chunk=id_to_chunk,
        dim=DIM,
        retrieval=RetrievalConfig(**cfg),
    )


def test_full_pipeline_returns_final_k():
    bm25, store, id_to_chunk = _fixture()
    result = _search("容器冷启动", bm25, store, id_to_chunk, top_k=20, final_k=2, rerank_enabled=True)

    assert isinstance(result, RetrievalResult)
    assert len(result.results) == 2
    assert all(r.stage == "rerank" for r in result.results)


def test_rerank_disabled_keeps_rrf_stage():
    bm25, store, id_to_chunk = _fixture()
    result = _search(
        "容器冷启动", bm25, store, id_to_chunk,
        top_k=20, final_k=2, rerank_enabled=False,
    )

    assert len(result.results) == 2
    assert all(r.stage == "rrf" for r in result.results)


def test_rerank_disabled_by_default():
    # 第 19 轮消融结论：rerank 默认关闭（dense 余弦精排稳定负贡献）
    bm25, store, id_to_chunk = _fixture()
    result = _search("容器冷启动", bm25, store, id_to_chunk, top_k=20, final_k=2)

    assert all(r.stage == "rrf" for r in result.results)
    assert [s.name for s in result.trace.stages] == ["bm25", "dense", "fusion"]


def test_sparse_only():
    bm25, store, id_to_chunk = _fixture()
    result = _search(
        "容器冷启动", bm25, store, id_to_chunk,
        top_k=20, final_k=2, dense_enabled=False, rerank_enabled=True,
    )

    assert [s.name for s in result.trace.stages] == ["bm25", "fusion", "rerank"]


def test_dense_only():
    bm25, store, id_to_chunk = _fixture()
    result = _search(
        "容器冷启动", bm25, store, id_to_chunk,
        top_k=20, final_k=2, sparse_enabled=False, rerank_enabled=True,
    )

    assert [s.name for s in result.trace.stages] == ["dense", "fusion", "rerank"]


def test_both_legs_disabled():
    bm25, store, id_to_chunk = _fixture()
    result = _search(
        "容器冷启动", bm25, store, id_to_chunk,
        sparse_enabled=False, dense_enabled=False,
    )

    assert result.results == []
    assert result.trace.stages == []


def test_trace_stages_and_order():
    bm25, store, id_to_chunk = _fixture()
    result = _search("容器冷启动", bm25, store, id_to_chunk, top_k=20, final_k=2, rerank_enabled=True)

    assert [s.name for s in result.trace.stages] == ["bm25", "dense", "fusion", "rerank"]


def test_trace_candidate_counts():
    # 空 query：两条腿都返回 top_k 个全 0 分块（3 个 chunk），
    # 融合去重后 3 个，重排截断到 final_k=2 —— 候选数口径可精确断言
    bm25, store, id_to_chunk = _fixture()
    result = _search("", bm25, store, id_to_chunk, top_k=20, final_k=2, rerank_enabled=True)

    counts = {s.name: s.candidate_count for s in result.trace.stages}
    assert counts == {"bm25": 3, "dense": 3, "fusion": 3, "rerank": 2}


def test_trace_total_latency():
    bm25, store, id_to_chunk = _fixture()
    result = _search("容器冷启动", bm25, store, id_to_chunk, top_k=20, final_k=2)

    total = sum(s.latency_ms for s in result.trace.stages)
    assert result.trace.total_latency_ms() == pytest.approx(total)
    assert all(s.latency_ms >= 0 for s in result.trace.stages)
