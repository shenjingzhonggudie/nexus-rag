"""生成层：把检索结果组装成对用户的回答（Answer）。"""

from ragkit.config import LLMConfig
from ragkit.retrieval import RetrievalResult
from ragkit.schemas import Answer, Citation


def answer_question(
    question: str,
    result: RetrievalResult,
    *,
    llm: LLMConfig,
) -> Answer:
    """把检索结果组装成回答：证据转引用、空结果拒答、抽取式生成。

    Args:
        question: 用户问题，原样进 Answer.question。
        result: 检索流水线产物；results 已按最终分数降序，本层不再排序。
        llm: LLM 配置；provider=none 走抽取式（answer=最高分块原文），
            openai_compatible 尚未实现，显式拒绝。

    Returns:
        Answer: 拒答（results 为空）时 refused=True、answer 为空串、
            citations 为空；两种情形下 trace 都原样挂载 result.trace
            （拒答也挂——检索确实发生了，保留"为什么拒"的诊断能力）。

    Raises:
        NotImplementedError: llm.provider == "openai_compatible" 时抛出；
            配置是人的意图，静默降级成抽取式是谎报能力，宁可当场炸。
    """
    if llm.provider == "openai_compatible":
        raise NotImplementedError(
            "openai_compatible 尚未实现：当前生成层只有 provider=none 的抽取式回答"
        )

    if not result.results:
        # 拒答：检索跑了但结果为空（第 15 轮决策 3：只认空，分数阈值挂扩展）
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
    # confidence 是 rerank 余弦的搬运（决策 2），不是新评分系统
    return Answer(
        question=question,
        answer=result.results[0].chunk.text,
        citations=citations,
        refused=False,
        confidence=result.results[0].score,
        contexts=[sc.chunk.text for sc in result.results],
        trace=result.trace,
    )
