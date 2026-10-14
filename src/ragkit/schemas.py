"""核心数据结构：文档、片段、评分片段、引用、检索轨迹与回答，支持字典互转。"""

from dataclasses import dataclass, field
from typing import Any


def _require_fields(data: dict[str, Any], required_fields: tuple[str, ...]) -> None:
    """检查反序列化字典是否包含指定字段。

    Args:
        data: 待检查的输入字典。
        required_fields: 必须存在的字段名，按给定顺序报告。

    Returns:
        None: 所有字段存在时正常返回。

    Raises:
        ValueError: 有一个或多个必需字段缺失时抛出。
    """
    # 先统一报告缺失字段，避免后续字典索引抛出不一致的 KeyError。
    missing_fields = [name for name in required_fields if name not in data]
    if missing_fields:
        raise ValueError(f"Missing required field(s): {', '.join(missing_fields)}")


@dataclass
class Document:
    """表示从 Markdown、PDF 或其他数据源读取的一篇原始文档。

    Attributes:
        doc_id: 文档的稳定标识。
        source: 文档来源标识，通常是文件名或相对路径。
        text: 文档正文。
        title: 文档标题；未知时为空字符串。
        metadata: 加载器或调用方附加的文档元数据。
    """

    doc_id: str  # 文档的稳定标识。
    source: str  # 来源标识，通常是文件名或相对路径。
    text: str  # 原始正文文本。
    title: str = ""  # 文档标题；未知时为空字符串。
    metadata: dict[str, Any] = field(default_factory=dict)  # 文档扩展元数据。

    def to_dict(self) -> dict[str, Any]:
        """将文档序列化为字典。

        Returns:
            dict[str, Any]: 包含文档全部字段的字典；metadata 与对象共享同一
                字典对象，调用方不得通过返回值修改其内容。
        """
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "text": self.text,
            "title": self.title,
            "metadata": self.metadata,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        """从字典构造文档。

        Args:
            data: 包含文档字段的映射；doc_id、source、text 为必需字段。

        Returns:
            Document: 从字段值构造的文档；缺少的 title 和 metadata 使用默认值。

        Raises:
            ValueError: 缺少任一必需字段时抛出。
        """
        _require_fields(data, ("doc_id", "source", "text"))

        return cls(
            doc_id=data["doc_id"],
            source=data["source"],
            text=data["text"],
            title=data.get("title", ""),
            metadata=data.get("metadata", {}),
        )

@dataclass
class Chunk:
    """表示文档切分后的一个片段，是检索的基本文本单元。

    Attributes:
        chunk_id: 片段的稳定标识。
        doc_id: 该片段所属文档的标识。
        text: 片段正文。
        ordinal: 片段在所属文档中的顺序编号。
        score_hint: 可选的初始分数提示，默认为 0。
        title: 所属文档标题；未知时为空字符串。
        source: 所属文档来源标识。
        metadata: 分块策略附加的信息。
    """

    chunk_id: str  # 片段的稳定标识。
    doc_id: str  # 所属文档标识。
    text: str  # 片段正文。
    ordinal: int  # 在所属文档中的顺序编号。
    score_hint: float = 0.0  # 可选的初始分数提示。
    title: str = ""  # 所属文档标题。
    source: str = ""  # 所属文档来源标识。
    metadata: dict[str, Any] = field(default_factory=dict)  # 分块策略附加信息。

    def to_dict(self) -> dict[str, Any]:
        """将片段序列化为字典。

        Returns:
            dict[str, Any]: 包含片段全部字段的字典；metadata 与对象共享同一
                字典对象，调用方不得通过返回值修改其内容。
        """
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "text": self.text,
            "ordinal": self.ordinal,
            "score_hint": self.score_hint,
            "title": self.title,
            "source": self.source,
            "metadata": self.metadata,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chunk":
        """从字典构造片段。

        Args:
            data: 包含片段字段的映射；chunk_id、doc_id、text、ordinal 为必需字段。

        Returns:
            Chunk: 从字段值构造的片段；其余字段使用默认值。

        Raises:
            ValueError: 缺少任一必需字段时抛出。
        """
        _require_fields(data, ("chunk_id", "doc_id", "text", "ordinal"))

        return cls(
            chunk_id=data["chunk_id"],
            doc_id=data["doc_id"],
            text=data["text"],
            ordinal=data["ordinal"],
            score_hint=data.get("score_hint", 0.0),
            title=data.get("title", ""),
            source=data.get("source", ""),
            metadata=data.get("metadata", {}),
        )

@dataclass
class ScoredChunk:
    """表示一个带有检索分数和处理阶段信息的文档片段。

    Attributes:
        chunk: 被评分的文档片段。
        score: 当前处理阶段给出的综合分数。
        stage: 产生该分数的检索或排序阶段名称。
        sub_scores: 各子检索通道或打分项的分数。
    """

    chunk: Chunk  # 被评分的文档片段。
    score: float  # 当前阶段给出的综合分数。
    stage: str  # 产生分数的处理阶段。
    sub_scores: dict[str, float] = field(default_factory=dict)  # 子项分数。

    def to_dict(self) -> dict[str, Any]:
        """将评分片段序列化为字典。

        Returns:
            dict[str, Any]: 包含嵌套片段和分数信息的字典；sub_scores 与对象共享
                同一字典对象，调用方不得通过返回值修改其内容。
        """
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
            "stage": self.stage,
            "sub_scores": self.sub_scores,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoredChunk":
        """从字典构造评分片段。

        Args:
            data: 包含 chunk、score、stage 的映射；sub_scores 可省略。

        Returns:
            ScoredChunk: 将嵌套 chunk 字典转换为 Chunk 后构造的评分片段。

        Raises:
            ValueError: 缺少必需字段或嵌套 chunk 字段不全时抛出。
        """
        _require_fields(data, ("chunk", "score", "stage"))

        return cls(
            chunk=Chunk.from_dict(data["chunk"]),
            score=data["score"],
            stage=data["stage"],
            sub_scores=data.get("sub_scores", {}),
        )

@dataclass
class Citation:
    """表示回答中引用的一条来源证据。

    Attributes:
        index: 引用在回答中的编号。
        source: 证据来源标识。
        snippet: 引用的原文片段。
        title: 来源标题；未知时为空字符串。
    """

    index: int  # 引用在回答中的编号。
    source: str  # 证据来源标识。
    snippet: str  # 引用的原文片段。
    title: str = ""  # 来源标题。

    def to_dict(self) -> dict[str, Any]:
        """将引用序列化为字典。

        Returns:
            dict[str, Any]: 包含引用编号、来源、片段和标题的字典。
        """
        return {
            "index": self.index,
            "source": self.source,
            "snippet": self.snippet,
            "title": self.title,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Citation":
        """从字典构造引用。

        Args:
            data: 包含 index、source、snippet 的映射；title 可省略。

        Returns:
            Citation: 从字段值构造的引用。

        Raises:
            ValueError: 缺少任一必需字段时抛出。
        """
        _require_fields(data, ("index", "source", "snippet"))

        return cls(
            index=data["index"],
            source=data["source"],
            snippet=data["snippet"],
            title=data.get("title", ""),
        )

@dataclass
class StageTrace:
    """记录检索流水线中一个阶段的耗时和候选数量。

    Attributes:
        name: 阶段名称。
        latency_ms: 阶段耗时，单位为毫秒。
        candidate_count: 该阶段处理或产出的候选数量。
    """

    name: str  # 阶段名称。
    latency_ms: float = 0.0  # 阶段耗时，单位为毫秒。
    candidate_count: int = 0  # 该阶段处理或产出的候选数量。

    def to_dict(self) -> dict[str, Any]:
        """将阶段轨迹序列化为字典。

        Returns:
            dict[str, Any]: 包含阶段名称、耗时和候选数量的字典。
        """
        return {
            "name": self.name,
            "latency_ms": self.latency_ms,
            "candidate_count": self.candidate_count,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageTrace":
        """从字典构造阶段轨迹。

        Args:
            data: 包含阶段字段的映射；name 为必需字段。

        Returns:
            StageTrace: 从字段值构造的阶段轨迹；统计值缺省为 0。

        Raises:
            ValueError: 缺少 name 字段时抛出。
        """
        _require_fields(data, ("name",))

        return cls(
            name=data["name"],
            latency_ms=data.get("latency_ms", 0.0),
            candidate_count=data.get("candidate_count", 0),
        )

@dataclass
class RetrievalTrace:
    """记录一次检索过程中的全部阶段信息。

    Attributes:
        stages: 按执行顺序排列的检索阶段轨迹。
    """

    stages: list[StageTrace] = field(default_factory=list)  # 按执行顺序排列的阶段。

    def total_latency_ms(self) -> float:
        """计算所有阶段耗时之和。

        Returns:
            float: 所有阶段 latency_ms 的总和；没有阶段时为 0。
        """
        return sum(stage.latency_ms for stage in self.stages)

    def to_dict(self) -> dict[str, Any]:
        """将检索轨迹序列化为字典。

        Returns:
            dict[str, Any]: stages 字段为各阶段轨迹字典组成的列表。
        """
        return {
            "stages": [stage.to_dict() for stage in self.stages]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrievalTrace":
        """从字典构造检索轨迹。

        Args:
            data: 包含 stages 列表的映射；stages 缺失或为 None 时视为空列表。

        Returns:
            RetrievalTrace: 由映射中的阶段字典构成的轨迹。

        Raises:
            ValueError: 任一阶段字典缺少必需字段时抛出。
        """
        stages_data = data.get("stages")
        return cls(
            stages=[
                StageTrace.from_dict(stage_data)
                for stage_data in ([] if stages_data is None else stages_data)
            ]
        )

@dataclass
class Answer:
    """表示系统对用户问题生成的一次回答及其引用和检索轨迹。

    拒答时 refused=True、answer 为空串、citations 为空列表。contexts 是纯
    字符串列表，不是 Chunk 列表。trace=None 表示没有检索轨迹，序列化时为 null。

    Attributes:
        question: 用户提出的问题。
        answer: 系统生成的回答；拒答时为空字符串。
        citations: 回答引用的来源证据。
        refused: 回答是否为拒答。
        confidence: 系统对回答的置信度。
        contexts: 生成回答时使用的上下文纯文本列表。
        trace: 检索过程轨迹；没有运行检索时为 None。
    """

    question: str  # 用户提出的问题。
    answer: str  # 系统生成的回答；拒答时为空字符串。
    citations: list[Citation] = field(default_factory=list)  # 回答引用的来源证据。
    refused: bool = False  # 回答是否为拒答。
    confidence: float = 0.0  # 系统对回答的置信度。
    contexts: list[str] = field(default_factory=list)  # 生成回答时使用的纯文本上下文。
    trace: RetrievalTrace | None = None  # 检索过程轨迹；未检索时为 None。

    def to_dict(self) -> dict[str, Any]:
        """将回答序列化为字典。

        Returns:
            dict[str, Any]: 包含回答、引用和上下文的字典；嵌套对象被递归序列化，
                contexts 返回列表副本，trace 缺失时为 None。
        """
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": [citation.to_dict() for citation in self.citations],
            "refused": self.refused,
            "confidence": self.confidence,
            "contexts": self.contexts.copy(),
            "trace": self.trace.to_dict() if self.trace else None,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Answer":
        """从字典构造回答。

        Args:
            data: 包含 question、answer 的映射；其他字段可省略。citations 或
                contexts 缺失或为 None 时按空列表处理；trace 缺失或为 None 时
                保留为 None，非 None 的值按检索轨迹加载。

        Returns:
            Answer: 从映射构造的回答；其他可选字段使用默认值。

        Raises:
            ValueError: 缺少必需字段或引用/轨迹子对象缺少必需字段时抛出。
        """
        _require_fields(data, ("question", "answer"))
        citations_data = data.get("citations")
        contexts_data = data.get("contexts")
        trace_data = data.get("trace")

        return cls(
            question=data["question"],
            answer=data["answer"],
            citations=[
                Citation.from_dict(citation_data)
                for citation_data in ([] if citations_data is None else citations_data)
            ],
            refused=data.get("refused", False),
            confidence=data.get("confidence", 0.0),
            contexts=[] if contexts_data is None else contexts_data,
            trace=RetrievalTrace.from_dict(trace_data) if trace_data is not None else None,
        )
