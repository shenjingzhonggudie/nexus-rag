"""检索流水线：稀疏 / 稠密召回 → RRF 融合 → 可选精排，并记录各阶段轨迹。"""

import time

from ragkit.config import RetrievalConfig
from ragkit.retrieval.bm25 import BM25Index
from ragkit.retrieval.dense import dense_search
from ragkit.retrieval.fusion import rrf_fuse, weighted_fuse
from ragkit.retrieval.rerank import rerank
from ragkit.retrieval.result import RetrievalResult
from ragkit.schemas import Chunk, RetrievalTrace, ScoredChunk, StageTrace
from ragkit.stores import VectorStore


def search(
    query: str,
    *,
    bm25: BM25Index,
    store: VectorStore,
    id_to_chunk: dict[str, Chunk],
    dim: int,
    retrieval: RetrievalConfig,
) -> RetrievalResult:
    """按配置运行完整检索流水线。

    Args:
        query: 查询文本。
        bm25: 已建好的 BM25 索引。
        store: 向量库。
        id_to_chunk: chunk_id 到块对象的映射，供稠密检索还原块。
        dim: query 向量维度，必须与向量库一致。
        retrieval: 检索参数；sparse_enabled / dense_enabled 决定跑哪几路召回，
            rerank_enabled 决定是否精排，top_k 为召回与融合的候选数，
            final_k 为最终返回数。

    Returns:
        RetrievalResult: results 按最终分数降序、至多 final_k 个；trace 按
            实际执行顺序记录 bm25 / dense / fusion / rerank 阶段的耗时（毫秒）
            和候选数。两路召回都关闭时返回空结果和空 trace，不报错。
    """
    stages: list[StageTrace] = []

    def timed(name: str, fn) -> list[ScoredChunk]:
        """执行一个检索阶段，并把耗时和候选数追加到检索轨迹。

        Args:
            name: 写入轨迹的阶段名称。
            fn: 无参执行器，返回该阶段产生的候选块。

        Returns:
            list[ScoredChunk]: 原样返回执行器产出的候选块。
        """
        start = time.perf_counter()
        hits = fn()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        stages.append(StageTrace(name=name, latency_ms=elapsed_ms, candidate_count=len(hits)))
        return hits

    legs: list[list[ScoredChunk]] = []
    if retrieval.sparse_enabled:
        legs.append(timed("bm25", lambda: bm25.search(query, top_k=retrieval.top_k)))
    if retrieval.dense_enabled:
        legs.append(
            timed(
                "dense",
                lambda: dense_search(query, store, id_to_chunk, dim=dim, top_k=retrieval.top_k),
            )
        )
    if not legs:
        return RetrievalResult(results=[], trace=RetrievalTrace())

    if retrieval.fusion == "weighted":
        results = timed(
            "fusion",
            lambda: weighted_fuse(
                legs, alpha=retrieval.fusion_alpha, top_k=retrieval.top_k
            ),
        )
    else:
        results = timed("fusion", lambda: rrf_fuse(legs, top_k=retrieval.top_k))
    if retrieval.rerank_enabled:
        results = timed(
            "rerank",
            lambda: rerank(results, query, store, dim=dim, final_k=retrieval.final_k),
        )
    else:
        results = results[: retrieval.final_k]

    return RetrievalResult(results=results, trace=RetrievalTrace(stages=stages))
