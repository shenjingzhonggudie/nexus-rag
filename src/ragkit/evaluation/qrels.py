"""评测集加载：query + 相关文档标注（第 18 轮决策 2：文档级评测单元）。"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Qrel:
    """一条评测样例：一个问题 + 它应该命中的相关文档集合。

    Attributes:
        query: 自然语言问题。
        relevant: 相关 doc_id 集合（无序——相关性是成员关系，不分等级；
            分级相关度属 nDCG 扩展，当前评测只做 0/1 相关）。
    """

    query: str
    relevant: frozenset[str]


def load_qrels(path: Path) -> list[Qrel]:
    """读 JSON 评测集并校验。格式：`[{"query": str, "relevant": [doc_id, ...]}, ...]`

    Args:
        path: qrels.json 路径。

    Returns:
        list[Qrel]: 按文件顺序排列的评测样例；relevant 去重为 frozenset。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 顶层非列表，或某条缺 query / query 非非空 str /
            relevant 非非空列表 / 元素非 str 时抛出，消息带条目下标。
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"评测集顶层必须是列表，实际是 {type(data).__name__}")

    qrels: list[Qrel] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"第 {i} 条必须是对象，实际是 {type(item).__name__}")
        query = item.get("query")
        relevant = item.get("relevant")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"第 {i} 条缺少非空字符串 query")
        if not isinstance(relevant, list) or not relevant:
            raise ValueError(f"第 {i} 条缺少非空列表 relevant")
        if not all(isinstance(doc, str) and doc for doc in relevant):
            raise ValueError(f"第 {i} 条的 relevant 元素必须都是非空字符串")
        qrels.append(Qrel(query=query, relevant=frozenset(relevant)))
    return qrels
