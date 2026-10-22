"""评测标注：文档 + 小节字符范围（**不绑定切分结果**）。

为什么标字符范围而不是 chunk_id：chunk_id 是切分的产物，换 chunk_size 或
换分块策略（fixed / heading / 未来的 recursive）都会让它全部失效，标注就得
重做一遍。而"某个小节的字符区间"是文档的固有属性——只要文档本身不变，标注
就一直有效。评测时只判断「召回的块与答案小节的区间是否重叠」，因此换切分
不影响分数口径。

标注格式（qrels.json 的每一项）::

    {
      "query": "为什么组合索引要把选择性高的列放左边？",
      "type": "paraphrase",
      "answers": [
        {"doc": "mysql/组合索引.md", "section": "最左前缀原则",
         "start": 1234, "end": 2345}
      ]
    }

``answers`` 为空列表表示无答案 query（语料里没有对应内容，用于测拒答）。
"""

import json
from dataclasses import dataclass
from pathlib import Path

# 允许的 query 类型：与评测报告的分类统计口径一致
QUERY_TYPES = ("direct", "paraphrase", "multi_block", "cross_doc", "no_answer")


@dataclass(frozen=True)
class AnswerSection:
    """一条答案小节：文档 + 标题 + 规范化文本中的字符区间。

    Attributes:
        doc: 文档相对路径，与 ``Chunk.doc_id`` 同一口径。
        section: 小节标题，仅供人工核对与报告展示，**不参与匹配**。
        start: 区间起点（含），坐标系是 ``normalize_text(文档原文)`` 后的文本。
        end: 区间终点（不含）。
    """

    doc: str
    section: str
    start: int
    end: int

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


@dataclass(frozen=True)
class Qrel:
    """一条评测样例：问题 + 类型 + 若干答案小节。

    Attributes:
        query: 自然语言问题。
        type: query 类型，取值见 ``QUERY_TYPES``。
        answers: 答案小节元组；空元组表示无答案 query（用于测拒答）。
            多块综合 / 跨文档对比的问题会有多个条目。
        source: 题目来源。``internal`` = 读过正文出的题（答案保证可被该节回答）；
            ``external`` = 只看标题出的题（更接近真实用户问法）。报告按来源分组，
            用来看"出题视角"带来的差距。
        id: 稳定标识（如 ``q_0042``），用于复核日志 ``review_log.jsonl`` 的关联。
            **改了 query / 答案也保留同一个 id**：id 标识的是"这道题"，不是"这版标注"。
            允许为空（旧文件没有这个字段），为空时无法与复核日志关联。
    """

    query: str
    type: str = "direct"
    answers: tuple[AnswerSection, ...] = ()
    source: str = "internal"
    id: str = ""

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

    @property
    def is_no_answer(self) -> bool:
        """是否为无答案 query（用于拒答评测）。"""
        return not self.answers


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
        answers = tuple(
            AnswerSection(
                doc=str(answer["doc"]),
                section=str(answer.get("section", "")),
                start=int(answer["start"]),
                end=int(answer["end"]),
            )
            for answer in answers_raw
        )
        qrels.append(
            Qrel(
                query=str(item["query"]),
                type=str(item.get("type", "direct")),
                answers=answers,
                source=str(item.get("source", "internal")),
                id=str(item.get("id", "")),
            )
        )
    return qrels
