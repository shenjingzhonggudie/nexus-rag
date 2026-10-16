"""稠密（向量）检索：把 query 嵌入为向量，与向量库逐行做内积，取分数最高的块。"""

from ragkit.schemas import Chunk
from ragkit.stores import VectorStore
from ragkit.schemas import ScoredChunk
from ragkit.embeddings import embed_text

def dense_search(
    query: str,
    store: VectorStore,
    id_to_chunk: dict[str, Chunk],
    *,
    dim: int,
    top_k: int = 20,
) -> list[ScoredChunk]:
    """用向量内积对 query 与库中每个块打分，返回得分最高的 top_k 个块。

    嵌入向量已归一化时，内积等价于余弦相似度。

    Args:
        query: 查询文本。
        store: 向量库；matrix 的第 i 行对应 ids[i]。
        id_to_chunk: chunk_id 到块对象的映射，用于把向量库的 id 还原成 Chunk。
        dim: query 向量维度，必须与 store.matrix 的列数一致。
        top_k: 最多返回的块数。

    Returns:
        list[ScoredChunk]: 按分数从高到低排列，stage 为 "dense"，score 为
            Python float。向量库为空时返回空列表；空 query 不报错，
            各块分数为 0。

    Raises:
        KeyError: 向量库中的某个 chunk_id 不在 id_to_chunk 里（两者不同步）时抛出。
    """
    q = embed_text(query, dim=dim)
    # (N, dim) @ (dim,) → (N,)：一次算出 query 与全部块的内积。
    scores = store.matrix @ q
    # argsort 升序，[::-1] 反转成降序，再取前 top_k 个下标。
    top_indices = scores.argsort()[::-1][:top_k]
    result: list[ScoredChunk] = []
    for idx in top_indices:
        chunk_id = store.ids[idx]
        chunk = id_to_chunk[chunk_id]
        # numpy 标量转成 Python float，避免下游序列化出问题。
        score = float(scores[idx])
        result.append(ScoredChunk(chunk=chunk, score=score, stage="dense"))
    return result