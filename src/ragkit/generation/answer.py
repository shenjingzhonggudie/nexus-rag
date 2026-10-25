"""生成层：把检索结果组装成对用户的回答（Answer）。"""

from ragkit.config import LLMConfig
from ragkit.retrieval import RetrievalResult
from ragkit.schemas import Answer, Citation


def answer_question(
    question: str,
    result: RetrievalResult,
    *,
    llm: LLMConfig,
    refuse_threshold: float = 0.0,
) -> Answer:
    """把检索结果组装成回答：证据转引用、两类拒答判定、抽取式生成。

    Args:
        question: 用户问题，原样进 Answer.question。
        result: 检索流水线产物；results 已按最终分数降序，本层不再排序。
        llm: LLM 配置；provider=none 走抽取式（answer=最高分块原文），
            openai_compatible 尚未实现，显式拒绝。
        refuse_threshold: 拒答阈值，与 ``result.match_score``（查询实词被检索
            结果覆盖的比例）比较；0 表示不启用阈值判定。

    Returns:
        Answer: 拒答时 refused=True、answer 为空串、citations 为空；两种情形
            下 trace 都原样挂载 result.trace（拒答也挂——检索确实发生了，
            保留"为什么拒"的诊断能力）。

    Note:
        拒答有两类判据：① 检索结果为空（稀疏腿全部词不在语料时会发生）；
        ② ``match_score`` 低于阈值——稠密腿总会返回 top_k，所以"结果不为空"
        不代表"语料里有答案"；后者正是补上这个洞的关键。

    Raises:
        NotImplementedError: llm.provider == "openai_compatible" 时抛出；
            配置是人的意图，静默降级成抽取式是谎报能力，宁可当场炸。
    """
    if llm.provider == "openai_compatible":
        raise NotImplementedError(
            "openai_compatible 尚未实现：当前生成层只有 provider=none 的抽取式回答"
        )

    # 阈值判定只对有信号的情况生效：match_score=None 表示无法判定（不该拒答）
    below_threshold = (
        refuse_threshold > 0.0
        and result.match_score is not None
        and result.match_score < refuse_threshold
    )
    if not result.results or below_threshold:
        return Answer(
            question=question,
            answer="",
            citations=[],
            refused=True,
            confidence=0.0,
            contexts=[],
            trace=result.trace,
        )

    citations = [
        Citation(
            index=i + 1,
            source=sc.chunk.source,
            snippet=sc.chunk.text,
            title=sc.chunk.title,
        )
        for i, sc in enumerate(result.results)
    ]
    # provider="none" 的抽取式回答（第 15 轮决策 1）：answer = 最高分块原文；
    # confidence沿用最终排序分：融合排名分或重排logit（可负），不是概率。
    return Answer(
        question=question,
        answer=result.results[0].chunk.text,
        citations=citations,
        refused=False,
        confidence=result.results[0].score,
        contexts=[sc.chunk.text for sc in result.results],
        trace=result.trace,
    )
