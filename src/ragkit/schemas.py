from dataclasses import dataclass, field
from typing import Any


def _require_fields(data: dict[str, Any], required_fields: tuple[str, ...]) -> None:
    # 先统一报告缺失字段，避免后续字典索引抛出不一致的 KeyError。
    missing_fields = [name for name in required_fields if name not in data]
    if missing_fields:
        raise ValueError(f"Missing required field(s): {', '.join(missing_fields)}")


@dataclass
class Document:
    """表示一篇原始文档，通常来自 Markdown、PDF 或其他数据源。"""

    doc_id: str
    source: str
    text: str
    title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        """返回的 metadata 与对象共享同一字典对象，调用方不得修改其内容。"""
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "text": self.text,
            "title": self.title,
            "metadata": self.metadata,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
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
    """表示文档切分后的一个片段，是检索的基本文本单元。"""

    chunk_id: str
    doc_id: str
    text: str
    ordinal: int
    score_hint: float = 0.0
    title: str = ""
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        """返回的 metadata 与对象共享同一字典对象，调用方不得修改其内容。"""
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
    """表示一个带有检索分数和处理阶段信息的文档片段。"""

    chunk:Chunk
    score: float
    stage: str
    sub_scores: dict[str, float] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        """返回的 sub_scores 与对象共享同一字典对象，调用方不得修改其内容。"""
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
            "stage": self.stage,
            "sub_scores": self.sub_scores,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoredChunk":
        _require_fields(data, ("chunk", "score", "stage"))

        return cls(
            chunk=Chunk.from_dict(data["chunk"]),
            score=data["score"],
            stage=data["stage"],
            sub_scores=data.get("sub_scores", {}),
        )

@dataclass
class Citation:
    """表示回答中引用的一条来源证据。"""

    index: int
    source: str
    snippet: str
    title: str = ""
    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "source": self.source,
            "snippet": self.snippet,
            "title": self.title,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Citation":
        _require_fields(data, ("index", "source", "snippet"))

        return cls(
            index=data["index"],
            source=data["source"],
            snippet=data["snippet"],
            title=data.get("title", ""),
        )

@dataclass
class StageTrace:
    """记录检索流水线中一个阶段的耗时和候选数量。"""

    name: str
    latency_ms: float=0.0
    candidate_count: int=0
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "latency_ms": self.latency_ms,
            "candidate_count": self.candidate_count,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageTrace":
        _require_fields(data, ("name",))

        return cls(
            name=data["name"],
            latency_ms=data.get("latency_ms", 0.0),
            candidate_count=data.get("candidate_count", 0),
        )

@dataclass
class RetrievalTrace:
    """记录一次检索过程中的全部阶段信息。"""

    stages:list[StageTrace]=field(default_factory=list)
    def total_latency_ms(self) -> float:
        return sum(stage.latency_ms for stage in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": [stage.to_dict() for stage in self.stages]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrievalTrace":
        """宽容加载：stages 缺失或为 None（JSON null）时按空列表处理。"""
        stages_data = data.get("stages")
        return cls(
            stages=[
                StageTrace.from_dict(stage_data)
                for stage_data in ([] if stages_data is None else stages_data)
            ]
        )

@dataclass
class Answer:
    """表示系统对用户问题生成的一次回答及其引用和检索轨迹。"""

    """
    拒答时的表示：refused=True 时，answer 为空串、citations 为空列表。
    contexts 是纯字符串列表，不是 Chunk 列表
    trace=None 表示没有检索轨迹（如拒答或未运行检索流水线），序列化时保留为 null。
    """
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    refused: bool = False
    confidence: float = 0.0
    contexts: list[str] = field(default_factory=list)
    trace: RetrievalTrace | None = None
    def to_dict(self) -> dict[str, Any]:
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
        """宽容加载：citations、contexts 缺失或为 None 时按空列表处理。

        trace 缺失或为 None 时保留为 None，不调用 RetrievalTrace.from_dict；
        非 None 的 trace 按检索轨迹加载，空字典表示一个空轨迹。
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
