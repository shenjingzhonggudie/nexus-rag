"""评测指标：覆盖式 recall@k 与首个命中排名。

调用方提供命中的标注单元集合（``set[int]``序列）：v1是单块命中的小节，
v2是每个检索前缀联合支持的回答要点。函数只做集合汇总和排名计算，
证据的字符覆盖判定由evidence模块负责。
"""


def coverage_recall(hits_per_rank: list[set[int]], total: int, k: int) -> float:
    """前 k 个结果满足的答案单元比例（v1小节，v2回答要点）。

    Args:
        hits_per_rank: 单块或对应前缀已命中的标注单元索引集合。
        total: 该题标注单元总数。
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
    """首个非空命中位置的倒数；v2传入的是前缀要点命中序列。

    Args:
        hits_per_rank: 单块或对应前缀已命中的标注单元索引集合。

    Returns:
        float: 倒数排名，取值 (0, 1]；无命中返回 0.0。
    """
    for rank, hit_set in enumerate(hits_per_rank, start=1):
        if hit_set:
            return 1.0 / rank
    return 0.0
