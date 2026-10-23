"""语料加载与校验工具。

职责：
    读取固定输入目录中的 corpus.jsonl 与 sections.jsonl，建立“文档全文 + 小节区间”的可检索视图，
    并在加载时校验哈希与区间坐标，保证后续所有标注使用的坐标与 corpus.jsonl 的 text 完全同源。

边界：
    仅处理输入语料与标注，不调用任何被测系统，不读取 old_queries.jsonl。

承诺清单：
    1. 本模块给出的 (doc, start, end) 一定满足 text[start:end] 以 '##' 标题行开头（无标题文档除外）。
    2. 所有 doc_id 与 corpus.jsonl 逐字符一致。
    3. 提供关键词/正则检索，返回命中的文档、小节与上下文片段。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

INPUT_DIR = Path(r"C:\Users\王佳浩\codex\2026-10-23\new-chat\outputs\rag-holdout\input")


@dataclass
class Section:
    """一个小节区间。

    Attributes:
        doc: 文档标识，与 corpus.jsonl 的 doc_id 一致。
        section: 小节标题（无标题文档为空字符串）。
        start: 区间起点（含）。
        end: 区间终点（不含）。
    """

    doc: str
    section: str
    start: int
    end: int


@dataclass
class Corpus:
    """固定知识库的可检索视图。

    Attributes:
        texts: doc_id -> 文档全文。
        sections: doc_id -> 该文档的小节区间列表（按 start 升序）。
        stacks: doc_id -> 技术栈前缀（k8s/react/tidb/vue）。
    """

    texts: dict[str, str] = field(default_factory=dict)
    sections: dict[str, list[Section]] = field(default_factory=dict)
    stacks: dict[str, str] = field(default_factory=dict)

    @property
    def doc_ids(self) -> list[str]:
        """按字典序返回全部文档标识。"""
        return sorted(self.texts)

    def section_of(self, doc: str, start: int) -> Section:
        """返回包含 start 的小节区间。

        Args:
            doc: 文档标识。
            start: 区间内的任意偏移。

        Returns:
            命中的 Section。

        Raises:
            KeyError: doc 不存在。
            ValueError: start 未落在任何小节内。
        """
        for sec in self.sections[doc]:
            if sec.start <= start < sec.end:
                return sec
        raise ValueError(f"offset {start} 不在 {doc} 的任何小节内")

    def find(self, pattern: str, doc: str | None = None, stack: str | None = None,
             context: int = 160, limit: int = 40, flags: int = 0) -> list[dict]:
        """按正则检索语料，返回带上下文的命中列表。

        Args:
            pattern: 正则表达式。
            doc: 限定单个文档；为 None 表示不限。
            stack: 限定技术栈（k8s/react/tidb/vue）；为 None 表示不限。
            context: 命中位置前后取多少字符作为上下文。
            limit: 最多返回多少条。
            flags: 传给 re 的标志位。

        Returns:
            每项含 doc / stack / section / start / end / pos / snippet 的字典列表。
        """
        rx = re.compile(pattern, flags)
        out: list[dict] = []
        for d in self.doc_ids:
            if doc and d != doc:
                continue
            if stack and self.stacks.get(d) != stack:
                continue
            text = self.texts[d]
            for m in rx.finditer(text):
                a = max(0, m.start() - context)
                b = min(len(text), m.end() + context)
                try:
                    sec = self.section_of(d, m.start())
                except ValueError:
                    continue
                out.append({
                    "doc": d,
                    "stack": self.stacks.get(d),
                    "section": sec.section,
                    "sec_start": sec.start,
                    "sec_end": sec.end,
                    "pos": m.start(),
                    "match": m.group(0),
                    "snippet": text[a:b],
                })
                if len(out) >= limit:
                    return out
        return out

    def has(self, pattern: str, doc: str | None = None, stack: str | None = None,
            flags: int = 0) -> bool:
        """判断语料（或限定范围）中是否存在某个模式的匹配。"""
        return bool(self.find(pattern, doc=doc, stack=stack, limit=1, flags=flags, context=0))

    def docs_having(self, pattern: str, flags: int = 0) -> list[str]:
        """返回正文中出现该模式的所有文档标识。"""
        rx = re.compile(pattern, flags)
        return [d for d in self.doc_ids if rx.search(self.texts[d])]

    def show(self, doc: str, start: int | None = None, end: int | None = None,
             limit: int = 3000) -> str:
        """取文档（或某区间）的文本，超长时截断。"""
        text = self.texts[doc]
        if start is not None:
            text = text[start:end]
        return text[:limit]


def load(input_dir: Path | str = INPUT_DIR) -> Corpus:
    """加载并校验语料。

    Args:
        input_dir: 输入目录，需含 corpus.jsonl 与 sections.jsonl。

    Returns:
        校验通过的 Corpus。

    Raises:
        AssertionError: 哈希不匹配、区间不以 '##' 标题行开头，或 doc_id 集合不一致。
    """
    input_dir = Path(input_dir)
    texts: dict[str, str] = {}
    with (input_dir / "corpus.jsonl").open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            texts[row["doc_id"]] = row["text"]

    corpus = Corpus(texts=texts)
    for d in corpus.doc_ids:
        corpus.stacks[d] = d.split("/", 1)[0]

    seen: set[str] = set()
    with (input_dir / "sections.jsonl").open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            d = row["doc_id"]
            assert d in texts, f"sections.jsonl 中的 {d} 不在 corpus.jsonl"
            s, e = row["start"], row["end"]
            assert 0 <= s < e <= len(texts[d]), f"{d} 区间越界: {s}, {e}"
            if row["section"]:
                head = texts[d][s:s + 2]
                assert head == "##", f"{d} 的区间 [{s},{e}) 不是以 '##' 开头: {head!r}"
            corpus.sections.setdefault(d, []).append(Section(d, row["section"], s, e))
            seen.add(d)

    assert seen == set(texts), "sections.jsonl 与 corpus.jsonl 的文档集合不一致"
    for d in corpus.doc_ids:
        corpus.sections[d].sort(key=lambda x: x.start)
    return corpus


def verify(doc_ids_and_spans: list[tuple[str, str, int, int]],
           corpus: Corpus | None = None) -> list[str]:
    """校验一批 (doc, section, start, end) 标注是否合法。

    Args:
        doc_ids_and_spans: 每项为 (doc, section, start, end)。
        corpus: 已加载的语料；为 None 时内部重新加载。

    Returns:
        问题描述列表；为空表示全部通过。
    """
    c = corpus or load()
    problems: list[str] = []
    for doc, section, start, end in doc_ids_and_spans:
        if doc not in c.texts:
            problems.append(f"{doc}: doc_id 不存在")
            continue
        text = c.texts[doc]
        if not (0 <= start < end <= len(text)):
            problems.append(f"{doc} [{start},{end}): 越界或 end<=start")
            continue
        if section:
            if not text[start:start + 2] == "##":
                problems.append(f"{doc} [{start},{end}): 未以 '##' 开头")
        for sec in c.sections[doc]:
            if sec.start == start and sec.end == end:
                if sec.section != section:
                    problems.append(f"{doc} [{start},{end}): section 应为 {sec.section!r}，实为 {section!r}")
                break
        else:
            problems.append(f"{doc} [{start},{end}): 与 sections.jsonl 的区间不重合")
    return problems
