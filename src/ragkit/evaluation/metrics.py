def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """计算前 k 个检索结果的召回率。

    Args:
        retrieved: 按相关性排序的检索结果 ID 列表。
        relevant: 真实相关的文档 ID 集合。
        k: 截断位置，只考虑前 k 个检索结果。

    Returns:
        float: 前 k 个检索结果的召回率，取值范围 [0, 1]。
    """
    if k <= 0:
        raise ValueError("k must be a positive integer")
    if not relevant:
        return 0.0
    retrieved_at_k = retrieved[:k]
    hits = sum(1 for doc_id in retrieved_at_k if doc_id in relevant)
    return hits / len(relevant)


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    """第一个相关文档所在位置 rank 的倒数（1/rank）；无命中返回 0.0。

    Args:
        retrieved: 按相关性排序的检索结果 ID 列表。
        relevant: 真实相关的文档 ID 集合。

    Returns:
        float: 第一个相关文档的倒数排名，取值范围 [0, 1]。
    """
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0