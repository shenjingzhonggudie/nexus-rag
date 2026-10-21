"""按 Markdown 二级标题切分：每个 ## 小节成为一个独立的片段；超长小节用 fixed 再切。"""

import re

from .fixed import iter_spans

_HEADING_RE = re.compile(r"^##[ \t]+", re.MULTILINE)

# 超长小节再切参数
_SPLIT_THRESHOLD = 400  # 小节超过该字符数则启用 fixed 再切
_SPLIT_CHUNK_SIZE = 300  # 再切时的目标块长


def iter_heading_sections(text: str) -> list[tuple[int, int]]:
    """按 Markdown 二级标题（##）切分，返回每个原始小节的半开区间（不触发再切）。

    每个区间从一个 ``##`` 标题行开始，到下一个 ``##`` 标题行之前（或文本
    末尾）。第一个 ``##`` 之前的文本（文档一级标题 ``#`` 与可能的引言）不
    单独成块——主标题已由加载层提取为文档 title，正文里从第一个 ``##`` 起。
    没有 ``##`` 标题时，整个非空文本作为单块。

    Args:
        text: 待切分的原始文本（应为 normalize_text 之后的文本）。

    Returns:
        list[tuple[int, int]]: 按文本顺序排列的 (start, end) 半开区间，可
            直接用 text[start:end] 取出该小节（含其 ``##`` 标题行）。
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [(0, len(text))] if text else []

    spans: list[tuple[int, int]] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((start, end))
    return spans


def iter_heading_spans(text: str) -> list[tuple[int, int]]:
    """按 ## 标题切分，超长小节用 fixed 再切，返回最终块区间。

    单个小节长度超过 ``_SPLIT_THRESHOLD`` 时，用 fixed 策略（目标块长
    ``_SPLIT_CHUNK_SIZE``、无重叠）再切成多个块，避免产生过长的块。其余
    小节原样保留为一个块。

    Args:
        text: 待切分的原始文本（应为 normalize_text 之后的文本）。

    Returns:
        list[tuple[int, int]]: 按文本顺序排列的 (start, end) 半开区间，可
            直接用 text[start:end] 取出对应片段。
    """
    return [
        span
        for start, end in iter_heading_sections(text)
        for span in _split_long(start, end, text)
    ]


def _split_long(start: int, end: int, text: str) -> list[tuple[int, int]]:
    """小节长度不超过阈值时原样返回；否则用 fixed 策略再切为多个块。"""
    if end - start <= _SPLIT_THRESHOLD:
        return [(start, end)]
    sub_spans = iter_spans(
        text[start:end], chunk_size=_SPLIT_CHUNK_SIZE, overlap=0
    )
    return [(start + s, start + e) for s, e in sub_spans]
