"""稀疏/稠密召回 → 排名融合 → 可选query-document重排 → 最终候选。"""

import time

from ragkit.config import RerankConfig, RetrievalConfig
from ragkit.retrieval.bm25 import BM25Index
from ragkit.retrieval.dense import dense_search
from ragkit.retrieval.fusion import rrf_fuse, weighted_rrf_fuse
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
    rerank_config: RerankConfig | None = None,
) -> RetrievalResult:
    """按配置运行完整检索流水线。

    Args:
        query: 查询文本。
        bm25: 已建好的 BM25 索引。
        store: 向量库。
        id_to_chunk: chunk_id 到块对象的映射，供稠密检索还原块。
        dim: query 向量维度，必须与向量库一致。
        retrieval: 检索参数；sparse_enabled / dense_enabled 决定跑哪几路召回，
            fusion_method决定融合方式，top_k为每路召回与融合后的候选上限，
            final_k 为最终返回数。
        rerank_config: 独立的模型重排配置；None或enabled=False时只运行融合。

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
    bm25_hits: list[ScoredChunk] = []
    if retrieval.sparse_enabled:
        bm25_hits = timed("bm25", lambda: bm25.search(query, top_k=retrieval.top_k))
        legs.append(bm25_hits)
    if retrieval.dense_enabled:
        legs.append(
            timed(
                "dense",
                lambda: dense_search(query, store, id_to_chunk, dim=dim, top_k=retrieval.top_k),
            )
        )
    if not legs:
        return RetrievalResult(results=[], trace=RetrievalTrace(), match_score=0.0)

    # 拒答判据（两层）：① 语料里完全没出现过的英文实体（Kafka / JVM）→ 强制 0；
    # ② 否则用实词覆盖率。不能用融合分——它是排名分（0.012~0.017），只反映名次。
    match_score: float | None = None
    if retrieval.sparse_enabled:
        if bm25.unknown_entities(query):
            match_score = 0.0
        else:
            match_score = bm25.key_term_coverage(query, bm25_hits)

    if retrieval.fusion_method == "weighted_rrf":
        candidates = timed(
            "fusion",
            lambda: weighted_rrf_fuse(
                legs, alpha=retrieval.fusion_alpha, top_k=retrieval.top_k
            ),
        )
    else:
        candidates = timed("fusion", lambda: rrf_fuse(legs, top_k=retrieval.top_k))

    # 先保留top_k给独立模型，不能先截成final_k再让模型重新排这几条。
    if rerank_config is not None and rerank_config.enabled:
        results = timed(
            "rerank",
            lambda: rerank(
                query, candidates, final_k=retrieval.final_k,
                model_name=rerank_config.model_name, batch_size=rerank_config.batch_size,
                max_length=rerank_config.max_length, device=rerank_config.device,
                local_files_only=rerank_config.local_files_only,
            ),
        )
    else:
        results = candidates[:retrieval.final_k]

    return RetrievalResult(
        results=results,
        trace=RetrievalTrace(stages=stages),
        match_score=match_score,
    )
