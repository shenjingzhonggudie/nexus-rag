"""检索流水线的返回结果：最终排序结果 + 检索轨迹。"""

from dataclasses import dataclass

from ragkit.schemas import RetrievalTrace, ScoredChunk


@dataclass
class RetrievalResult:
    """一次检索的最终产物。

    Attributes:
        results: 按最终分数降序排列的块，长度通常为 final_k。
        trace: 本次检索各阶段的耗时与候选数（未运行任何阶段时为空）。
    """

    results: list[ScoredChunk]
    trace: RetrievalTrace
