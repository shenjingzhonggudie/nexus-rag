"""评测标注：v1小节区间；v2回答要点及其最小充分证据。

v2 的 answers 每项含 point 和 evidence；同一要点的所有证据均为必要条件。
证据坐标基于 normalize_text(load_file(path).text)，quote 保留对应原文。
旧格式保留原判分契约，避免改写历史实验的含义。
"""

import json
from dataclasses import dataclass
from pathlib import Path

# 允许的 query 类型：与评测报告的分类统计口径一致
QUERY_TYPES = ("direct", "paraphrase", "multi_block", "cross_doc", "no_answer")


@dataclass(frozen=True)
class AnswerSection:
    """文档中的一个区间：v1为小节，v2为具体证据原文。

    Attributes:
        doc: 文档相对路径，与 ``Chunk.doc_id`` 同一口径。
        section: 小节标题，仅供人工核对与报告展示，**不参与匹配**。
        start: 区间起点（含），基于 ``normalize_text(load_file(path).text)``。
        end: 区间终点（不含）。
    """

    doc: str
    section: str
    start: int
    end: int
    quote: str = ""

    def __post_init__(self) -> None:
        """校验区间合法。

        Raises:
            ValueError: doc 为空、start 为负、或 end 不大于 start 时抛出。
        """
        if not self.doc.strip():
            raise ValueError("AnswerSection.doc 不能为空")
        if self.start < 0 or self.end <= self.start:
            raise ValueError(
                f"AnswerSection 区间非法：start={self.start} end={self.end}"
            )
        if self.quote and len(self.quote) != self.end - self.start:
            raise ValueError("证据 quote 长度必须等于 end-start")


@dataclass(frozen=True)
class AnswerPoint:
    """一个必要回答要点；evidence 中每个区间都需要命中。"""

    point: str
    evidence: tuple[AnswerSection, ...]

    def __post_init__(self) -> None:
        if not self.point.strip() or not self.evidence:
            raise ValueError("回答要点及其证据不能为空")
        if any(not e.quote.strip() for e in self.evidence):
            raise ValueError("v2证据必须包含非空原文 quote")


@dataclass(frozen=True)
class Qrel:
    """一条评测样例，保留版本、来源和标注复核状态。

    Attributes:
        query: 自然语言问题。
        type: query 类型，取值见 ``QUERY_TYPES``。
        answers: v1为小节；v2为answer_points各要点证据的扁平视图。
        source: internal参考正文出题，external仅参考标题出题，不保证标签正确。
        id: 稳定标识（如 ``q_0042``），用于复核日志 ``review_log.jsonl`` 的关联。
            **改了 query / 答案也保留同一个 id**：id 标识的是"这道题"，不是"这版标注"。
            允许为空（旧文件没有这个字段），为空时无法与复核日志关联。
    """

    query: str
    type: str = "direct"
    answers: tuple[AnswerSection, ...] = ()
    source: str = "internal"
    id: str = ""
    annotation_version: int = 1
    answer_points: tuple[AnswerPoint, ...] = ()
    annotation_status: str = "complete"
    unanswerable_reason: str = ""

    def __post_init__(self) -> None:
        """校验问题与类型。

        Raises:
            ValueError: query 为空、或 type 不在允许集合内时抛出。
        """
        if not self.query.strip():
            raise ValueError("Qrel.query 不能为空")
        if self.type not in QUERY_TYPES:
            raise ValueError(
                f"未知的 query 类型 {self.type!r}，允许：{QUERY_TYPES}"
            )
        if self.annotation_version not in (1, 2):
            raise ValueError("annotation_version 只支持1或2")
        if self.annotation_status not in ("complete", "needs_review", "retained_no_answer"):
            raise ValueError("未知 annotation_status")
        if self.annotation_version == 2:
            if self.type == "no_answer":
                if self.answers or self.answer_points:
                    raise ValueError("无答案题不能附答案证据")
                if not self.unanswerable_reason.strip():
                    raise ValueError("v2无答案题须说明缺失的回答信息")
            elif self.annotation_status == "retained_no_answer":
                raise ValueError("retained_no_answer 仅用于无答案题")
            elif self.annotation_status == "complete" and not self.answer_points:
                raise ValueError("v2有答案题必须有回答要点，不能静默视作无答案")

    @property
    def is_no_answer(self) -> bool:
        """是否为无答案 query（用于拒答评测）。"""
        if self.annotation_version == 2:
            return self.type == "no_answer"
        return not self.answers

    @property
    def is_evaluable(self) -> bool:
        return self.annotation_status != "needs_review"


def load_qrels(path: Path) -> list[Qrel]:
    """从 JSON 文件加载评测标注。

    Args:
        path: qrels.json 路径。

    Returns:
        list[Qrel]: 解析后的评测样例，顺序与文件一致。

    Raises:
        FileNotFoundError: 文件不存在时抛出。
        ValueError: 顶层不是列表、条目缺字段、或区间非法时抛出。
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("qrels 顶层必须是列表")

    qrels: list[Qrel] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 条 qrel 不是对象")
        answers_raw = item.get("answers", [])
        if not isinstance(answers_raw, list):
            raise ValueError(f"第 {index} 条 qrel 的 answers 必须是列表")
        version = int(item.get("annotation_version", 1))

        def section(answer: dict) -> AnswerSection:
            if not isinstance(answer, dict):
                raise ValueError("证据必须是对象")
            return AnswerSection(
                doc=str(answer["doc"]), section=str(answer.get("section", "")),
                start=int(answer["start"]), end=int(answer["end"]),
                quote=str(answer.get("quote", "")),
            )

        points: tuple[AnswerPoint, ...] = ()
        if version == 2:
            parsed_points = []
            for answer in answers_raw:
                if not isinstance(answer, dict) or not isinstance(answer.get("evidence"), list):
                    raise ValueError("v2答案须包含 point 和 evidence 列表")
                parsed_points.append(AnswerPoint(
                    point=str(answer["point"]),
                    evidence=tuple(section(e) for e in answer["evidence"]),
                ))
            points = tuple(parsed_points)
            answers = tuple(e for p in points for e in p.evidence)
        else:
            answers = tuple(section(answer) for answer in answers_raw)
        qrels.append(
            Qrel(
                query=str(item["query"]),
                type=str(item.get("type", "direct")),
                answers=answers,
                source=str(item.get("source", "internal")),
                id=str(item.get("id", "")),
                annotation_version=version,
                answer_points=points,
                annotation_status=str(item.get("annotation_status", "complete")),
                unanswerable_reason=str(item.get("unanswerable_reason", "")),
            )
        )
    return qrels
