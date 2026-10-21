from ragkit.schemas import ScoredChunk, Chunk

def rrf_fuse(
    results: list[list[ScoredChunk]],
    *,
    k: int = 60,
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


# 加权排名融合（weighted_fuse）已移至 rerank.py：加权融合属于"精排/重排"阶段的职责，
# 与等权 RRF（纯召回合并）分开，避免两份几乎相同的实现。