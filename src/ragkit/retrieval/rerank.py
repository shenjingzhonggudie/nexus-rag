"""精排：用向量库里的向量对候选块重新打分并截断。"""

from ragkit.embeddings import embed_text
from ragkit.schemas import ScoredChunk
from ragkit.stores import VectorStore


def rerank(
    candidates: list[ScoredChunk],
    query: str,
    store: VectorStore,
    *,
    dim: int,
    final_k: int,
) -> list[ScoredChunk]:
    """用 query 向量与候选块向量的内积重新打分，保留得分最高的 final_k 个。

    Args:
        candidates: 待精排的候选块，通常是融合后的结果；不会被修改。
        query: 查询文本。
        store: 向量库；候选块按 chunk_id 在其中查找对应向量。
        dim: query 向量维度，必须与向量库一致。
        final_k: 最多保留的块数。

    Returns:
        list[ScoredChunk]: 按精排分数从高到低排列，stage 为 "rerank"，
            sub_scores 中的 "prev" 记录精排前的分数。不在向量库中的候选
            无法打分，会被丢弃。
    """
    q = embed_text(query, dim=dim)
    row_of = {chunk_id: row for row, chunk_id in enumerate(store.ids)}

    reranked: list[ScoredChunk] = []
    for c in candidates:
        row = row_of.get(c.chunk.chunk_id)
        if row is None:
            continue
        reranked.append(
            ScoredChunk(
                chunk=c.chunk,
                score=float(store.matrix[row] @ q),
                stage="rerank",
                sub_scores={**c.sub_scores, "prev": c.score},
            )
        )
    reranked.sort(key=lambda x: x.score, reverse=True)
    return reranked[:final_k]