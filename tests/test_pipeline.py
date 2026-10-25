"""检索流水线的契约测试：开关组合、trace 阶段与候选数口径、返回类型。"""

import numpy as np
import pytest

from ragkit.config import RerankConfig, RetrievalConfig
from ragkit.embeddings import embed_text
from ragkit.retrieval.bm25 import BM25Index
from ragkit.retrieval.pipeline import search
from ragkit.retrieval.result import RetrievalResult
from ragkit.schemas import Chunk, ScoredChunk
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


def _search(query, bm25, store, id_to_chunk, *, rerank_config=None, **cfg):
    return search(
        query,
        bm25=bm25,
        store=store,
        id_to_chunk=id_to_chunk,
        dim=DIM,
        retrieval=RetrievalConfig(**cfg),
        rerank_config=rerank_config,
    )


def test_full_pipeline_returns_final_k():
    bm25, store, id_to_chunk = _fixture()
    result = _search("容器冷启动", bm25, store, id_to_chunk, top_k=20, final_k=2)

    assert isinstance(result, RetrievalResult)
    assert len(result.results) == 2
    assert all(r.stage == "weighted_rrf" for r in result.results)


def test_equal_fusion_keeps_rrf_stage():
    bm25, store, id_to_chunk = _fixture()
    result = _search(
        "容器冷启动", bm25, store, id_to_chunk,
        top_k=20, final_k=2, fusion_method="rrf",
    )

    assert len(result.results) == 2
    assert all(r.stage == "rrf" for r in result.results)


def test_weighted_fusion_default_does_not_call_reranker(monkeypatch):
    import importlib
    pipeline = importlib.import_module("ragkit.retrieval.pipeline")
    def unexpected_model(*args, **kwargs):
        raise AssertionError("default query must not call a model reranker")
    monkeypatch.setattr(pipeline, "rerank", unexpected_model)
    bm25, store, id_to_chunk = _fixture()
    result = _search("容器冷启动", bm25, store, id_to_chunk, top_k=20, final_k=2)

    assert all(r.stage == "weighted_rrf" for r in result.results)
    assert [s.name for s in result.trace.stages] == ["bm25", "dense", "fusion"]


def test_sparse_only():
    bm25, store, id_to_chunk = _fixture()
    result = _search(
        "容器冷启动", bm25, store, id_to_chunk,
        top_k=20, final_k=2, dense_enabled=False,
    )

    assert [s.name for s in result.trace.stages] == ["bm25", "fusion"]


def test_dense_only():
    bm25, store, id_to_chunk = _fixture()
    result = _search(
        "容器冷启动", bm25, store, id_to_chunk,
        top_k=20, final_k=2, sparse_enabled=False,
    )

    assert [s.name for s in result.trace.stages] == ["dense", "fusion"]


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
    result = _search("容器冷启动", bm25, store, id_to_chunk, top_k=20, final_k=2)

    assert [s.name for s in result.trace.stages] == ["bm25", "dense", "fusion"]


def test_trace_candidate_counts():
    # 空 query：两条腿都返回 top_k 个全 0 分块（3 个 chunk），
    # 融合去重后3个，默认不运行模型；最终截成2个。
    bm25, store, id_to_chunk = _fixture()
    result = _search("", bm25, store, id_to_chunk, top_k=20, final_k=2)

    counts = {s.name: s.candidate_count for s in result.trace.stages}
    assert counts == {"bm25": 3, "dense": 3, "fusion": 3}
    assert len(result.results) == 2


def test_trace_total_latency():
    bm25, store, id_to_chunk = _fixture()
    result = _search("容器冷启动", bm25, store, id_to_chunk, top_k=20, final_k=2)

    total = sum(s.latency_ms for s in result.trace.stages)
    assert result.trace.total_latency_ms() == pytest.approx(total)
    assert all(s.latency_ms >= 0 for s in result.trace.stages)


def test_model_receives_fusion_pool_before_final_k_and_trace_is_separate(monkeypatch):
    import importlib
    pipeline = importlib.import_module("ragkit.retrieval.pipeline")
    bm25, store, chunks = _fixture()
    baseline = _search("容器冷启动", bm25, store, chunks, top_k=3, final_k=1)
    seen = {}
    def score(query, candidates, **kwargs):
        seen.update(query=query, candidates=candidates, options=kwargs)
        # 提升融合末名，证明模型有机会看到final_k之外的候选。
        return [ScoredChunk(chunk=candidates[-1].chunk, score=-5.0, stage="rerank")]
    monkeypatch.setattr(pipeline, "rerank", score)
    result = _search("容器冷启动", bm25, store, chunks, top_k=3, final_k=1,
                     rerank_config=RerankConfig(enabled=True))
    assert seen["query"] == "容器冷启动"
    assert len(seen["candidates"]) == 3
    assert seen["options"]["final_k"] == 1
    assert result.results[0].chunk.chunk_id != baseline.results[0].chunk.chunk_id
    assert result.match_score == baseline.match_score
    assert [(s.name,s.candidate_count) for s in result.trace.stages] == [
        ("bm25",1),("dense",3),("fusion",3),("rerank",1)]


def test_model_failure_propagates_without_fusion_fallback(monkeypatch):
    import importlib
    from ragkit.errors import RerankError
    pipeline = importlib.import_module("ragkit.retrieval.pipeline")
    def fail(*args, **kwargs):
        raise RerankError("missing local reranker")
    monkeypatch.setattr(pipeline, "rerank", fail)
    bm25, store, chunks = _fixture()
    with pytest.raises(RerankError, match="missing local"):
        _search("容器冷启动",bm25,store,chunks,rerank_config=RerankConfig(enabled=True))
