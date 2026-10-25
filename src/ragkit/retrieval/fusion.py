"""排名融合：按各路候选的名次合并结果，不重新计算 query-document 相关性。"""

from ragkit.schemas import Chunk, ScoredChunk

DEFAULT_ALPHA = 0.9
DEFAULT_RRF_K = 60


def rrf_fuse(
    results: list[list[ScoredChunk]],
    *,
    k: int = DEFAULT_RRF_K,
    top_k: int = 20,
) -> list[ScoredChunk]:
    """Reciprocal Rank Fusion (RRF) for combining multiple retrieval results.

    Args:
        results: 每个元素是一个检索器返回的 ScoredChunk 列表。
        k: RRF 中的常数，默认 60。
        top_k: 最多返回的块数。

    Returns:
        list[ScoredChunk]: 按融合后的分数从高到低排列的块列表。
    """

    # 以 chunk_id 为键去重：同一块被多个通道召回时，RRF 分数累加、块对象只保留一份
    fused: dict[str, tuple[Chunk, float]] = {}
    for result in results:
        for rank, scored_chunk in enumerate(result, start=1):
            cid = scored_chunk.chunk.chunk_id
            chunk, prev = fused.get(cid, (scored_chunk.chunk, 0.0))
            fused[cid] = (chunk, prev + 1.0 / (k + rank))

    fused_list = [
        ScoredChunk(chunk=chunk, score=score, stage="rrf")
        for chunk, score in fused.values()
    ]
    fused_list.sort(key=lambda x: x.score, reverse=True)
    return fused_list[:top_k]


def weighted_rrf_fuse(
    legs: list[list[ScoredChunk]],
    *,
    alpha: float = DEFAULT_ALPHA,
    k: int = DEFAULT_RRF_K,
    top_k: int = 20,
) -> list[ScoredChunk]:
    """按加权倒数排名分 ``Σ w_i/(k+rank_i)`` 融合候选，并取前 top_k 个。

    Args:
        legs: 各路召回结果，双路时顺序为 [BM25, dense]；各路列表顺序即名次。
        alpha: 双路时第一路（BM25）的权重，第二路权重为 1-alpha。
            0.5 时与等权 RRF 排序一致，分数为其一半。
        k: 倒数排名分常数，默认 60。
        top_k: 融合后最多保留的候选数，供后续可选重排或最终截取使用。

    Returns:
        list[ScoredChunk]: 按融合分降序，stage 为 "weighted_rrf"；同一 chunk_id
            的分数累加，并保留首次出现的块对象。同分时保留首次出现顺序。

    Note:
        单路时权重归一化为 1，alpha 不参与；多于两路时退化为等权平均。
        原始检索分数不参与计算；零权重路的候选仍保留，只是该路贡献为零。
    """
    n = len(legs)
    if n == 0:
        return []
    if n == 1:
        weights = [1.0]
    elif n == 2:
        weights = [alpha, 1.0 - alpha]
    else:
        weights = [1.0 / n] * n

    fused: dict[str, tuple[Chunk, float]] = {}
    for leg, weight in zip(legs, weights):
        for rank, scored in enumerate(leg, start=1):
            cid = scored.chunk.chunk_id
            chunk, prev = fused.get(cid, (scored.chunk, 0.0))
            fused[cid] = (chunk, prev + weight / (k + rank))

    results = [
        ScoredChunk(chunk=chunk, score=score, stage="weighted_rrf")
        for chunk, score in fused.values()
    ]
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:top_k]
