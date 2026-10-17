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


def weighted_fuse(
    results: list[list[ScoredChunk]],
    *,
    alpha: float = 0.9,
    k: int = 60,
    top_k: int = 20,
) -> list[ScoredChunk]:
    """加权排名融合：S(d) = α·S1(d) + (1-α)·S2(d)。

    S_i 是第 i 条腿的 RRF 排名分 1/(k+rank)；第一腿（BM25）权重 α、
    第二腿（dense）权重 1-α。α=0.5 时与等权 RRF 等价（差一个常数因子）。
    单腿时退化为该腿的排名排序（α 不参与，权重归一化为 1）。

    Args:
        results: 每个元素是一条腿返回的 ScoredChunk 列表，顺序为 [BM25, dense]。
        alpha: 第一条腿（BM25）的权重，取值 0~1；默认 0.9（BM25 为主）。
        k: RRF 常数，默认 60。
        top_k: 最多返回的块数。

    Returns:
        list[ScoredChunk]: 按加权融合分从高到低排列，stage 为 "rrf"。
    """
    n = len(results)
    if n == 1:
        weights = [1.0]
    elif n == 2:
        weights = [alpha, 1.0 - alpha]
    else:
        # 多于两腿时暂退化为等权（当前系统只有 BM25 + dense 两条腿）
        weights = [1.0 / n] * n

    fused: dict[str, tuple[Chunk, float]] = {}
    for result, w in zip(results, weights):
        for rank, scored_chunk in enumerate(result, start=1):
            cid = scored_chunk.chunk.chunk_id
            chunk, prev = fused.get(cid, (scored_chunk.chunk, 0.0))
            fused[cid] = (chunk, prev + w / (k + rank))

    fused_list = [
        ScoredChunk(chunk=chunk, score=score, stage="rrf")
        for chunk, score in fused.values()
    ]
    fused_list.sort(key=lambda x: x.score, reverse=True)
    return fused_list[:top_k]