"""评测指标：覆盖式 recall@k 与首个命中排名。

与"ID 集合交集"的传统写法不同，这里的检索结果被抽象为
**每个结果命中了哪些答案小节**（``set[int]`` 序列）——因为答案小节是字符
区间：一个块可能覆盖多个小节，也可能只与某个小节部分重叠（块边界随切分
变化）。把"是否命中"的判定留在调用方（需要 Chunk 的 doc_id 与字符偏移），
指标函数只做纯集合运算，保持可直测、无依赖。
"""


def coverage_recall(hits_per_rank: list[set[int]], total: int, k: int) -> float:
    """前 k 个结果覆盖了多少比例的答案小节。

    Args:
        hits_per_rank: 第 i 个检索结果命中的答案小节索引集合。
        total: 答案小节总数。
        k: 截断位置，必须为正整数。

    Returns:
        float: 覆盖率，取值 [0, 1]；``total <= 0``（无答案 query）返回 0.0。

    Raises:
        ValueError: k 不是正整数时抛出。
    """
    if k <= 0:
        raise ValueError("k must be a positive integer")
    if total <= 0:
        return 0.0
    covered: set[int] = set()
    for hit_set in hits_per_rank[:k]:
        covered.update(hit_set)  # 用 update：set / list 都能接受（明细落盘是 list）
    return len(covered) / total


def first_hit_mrr(hits_per_rank: list[set[int]]) -> float:
    """第一个命中任意答案小节的结果的倒数排名（1/rank）；无命中返回 0.0。

    Args:
        hits_per_rank: 第 i 个检索结果命中的答案小节索引集合。

    Returns:
        float: 倒数排名，取值 (0, 1]；无命中返回 0.0。
    """
    for rank, hit_set in enumerate(hits_per_rank, start=1):
        if hit_set:
            return 1.0 / rank
    return 0.0
