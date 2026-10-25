"""检索流水线的返回结果：最终排序结果 + 检索轨迹 + 拒答判据。"""

from dataclasses import dataclass

from ragkit.schemas import RetrievalTrace, ScoredChunk


@dataclass
class RetrievalResult:
    """一次检索的最终产物。

    Attributes:
        results: 按最终分数降序排列的块，长度通常为 final_k。
        trace: 本次检索各阶段的耗时与候选数（未运行任何阶段时为空）。
        match_score: BM25原始命中前3块的查询实词IDF覆盖率（0~1），
            英文未知实体会强制为0，供生成层判定拒答；
            None 表示无法判定（稀疏腿未启用、或查询没有长度 ≥ 2 的实词）。
            它独立于融合与模型重排，不是最终相关性分或校准后的回答正确概率。
"""

    results: list[ScoredChunk]
    trace: RetrievalTrace
    match_score: float | None = None
