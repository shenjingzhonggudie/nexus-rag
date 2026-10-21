"""精排：把多路召回结果按加权排名融合重新排序。

实现说明
--------
早期版本用"query 向量与候选向量内积"重排，但那个分数与 dense 腿完全相同
（同一个 ``embed_text`` + 同一次点积），没有引入任何新信息，实测稳定负贡献
（recall@1 −0.039）——它只是把 BM25 主导的融合排序覆盖成纯 dense 排序。

现在改为**加权排名融合**：

    S(d) = α·S1(d) + (1−α)·S2(d)

其中 ``S_i(d) = 1/(k + rank_i(d))`` 是第 i 条腿的排名分，第一条腿（BM25）
权重 α、第二条腿（dense）权重 1−α。它保留了"BM25 为主"的先验，同时让 dense
按权重参与，而不是一票否决。
"""

from ragkit.schemas import Chunk, ScoredChunk

# 加权排名融合的权重分配规则写在这里，供测试与文档引用
DEFAULT_ALPHA = 0.9
DEFAULT_RRF_K = 60


def rerank(
    legs: list[list[ScoredChunk]],
    *,
    alpha: float = DEFAULT_ALPHA,
    k: int = DEFAULT_RRF_K,
    final_k: int,
) -> list[ScoredChunk]:
    """按 S(d) = α·S1(d) + (1−α)·S2(d) 融合多路召回并取前 final_k 个。

    Args:
        legs: 各路召回结果，顺序为 [BM25, dense]；每条腿内部按该腿分数降序。
        alpha: 第一条腿（BM25）的权重，取值 0~1。0.5 时与等权 RRF 等价
            （差一个常数因子）；1.0 表示完全忽略 dense，0.0 表示完全忽略 BM25。
        k: 排名分常数，默认 60（与 RRF 惯例一致，压低名次差异）。
        final_k: 最多保留的块数。

    Returns:
        list[ScoredChunk]: 按加权融合分降序，stage 为 "rerank"；同一 chunk 被多路
            召回时分数累加、块对象只保留一份。

    Note:
        单腿时权重归一化为 1（alpha 不参与），退化为"按该腿的名次排序"，与
        ``rrf_fuse`` 结果顺序一致——这样只开一路召回时，rerank 不会改变排序。
    """
    n = len(legs)
    if n == 0:
        return []
    if n == 1:
        weights = [1.0]
    elif n == 2:
        weights = [alpha, 1.0 - alpha]
    else:
        # 多于两腿时退化为等权（当前系统只有 BM25 + dense 两条腿）
        weights = [1.0 / n] * n

    fused: dict[str, tuple[Chunk, float]] = {}
    for leg, weight in zip(legs, weights):
        for rank, scored in enumerate(leg, start=1):
            cid = scored.chunk.chunk_id
            chunk, prev = fused.get(cid, (scored.chunk, 0.0))
            fused[cid] = (chunk, prev + weight / (k + rank))

    results = [
        ScoredChunk(chunk=chunk, score=score, stage="rerank")
        for chunk, score in fused.values()
    ]
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:final_k]
