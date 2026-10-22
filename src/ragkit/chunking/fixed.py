"""固定长度切分：按目标长度和重叠量计算文本的切片区间。"""

_CJK_START = "\u4e00"
_CJK_END = "\u9fff"
# 英文字母按 3 个算 1 个字：中文技术文档里 "Kubernetes" 8 个字母占的篇幅
# 约等于 3 个汉字。
_LATIN_PER_WORD = 3


def _units(fragment: str) -> int:
    """内部计量单位：汉字 3、英文/数字/标点 1、空白 0。

    用整数而不是 ``1/3`` 浮点累加：``0.333... * 6`` 在浮点下等于
    ``1.9999999999999998``，会让"6 个字母 = 2 个字"判断失败、多切一个字符。
    对外展示仍用 :func:`effective_len`（除以 3 还原成"字"）。
    """
    total = 0
    for char in fragment:
        if char.isspace():
            continue
        total += 3 if _CJK_START <= char <= _CJK_END else 1
    return total


def effective_len(fragment: str) -> float:
    """计算文本的**有效长度**：汉字 1 个字，英文字母 3 个算 1 个字。

    空白不计（换行/缩进不代表内容量）。数字、标点、符号与英文同档。

    用途有二：① 切块时作为长度单位（``chunk_size=300`` 表示"约 300 个字"）；
    ② 过滤"字符数不少、信息量极低"的碎块——比如 React 文档里 ``</Sandpack>``
    这种独占一块的组件闭合标签：13 个字符，有效长度只有 4。

    Args:
        fragment: 待计量的文本片段。

    Returns:
        float: 有效长度（单位：字）。
    """
    return _units(fragment) / _LATIN_PER_WORD


def _end_of_budget(text: str, start: int, budget_units: int) -> int:
    """从 ``start`` 起累计整数刻度直到 ``budget_units``，返回字符下标。

    Args:
        text: 全文。
        start: 起点字符下标。
        budget_units: 目标刻度（1 字 = 3 刻度）。

    Returns:
        int: 字符下标（左闭右开区间的右端）。
    """
    accumulated = 0
    index = start
    length = len(text)
    while index < length and accumulated < budget_units:
        char = text[index]
        if not char.isspace():
            accumulated += 3 if _CJK_START <= char <= _CJK_END else 1
        index += 1
    return index


def iter_spans(text: str, *, chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    """按目标长度和重叠量生成文本的半开切片区间，不规范化文本。

    **长度按有效长度计量**：汉字算 1 个字，英文字母 3 个算 1 个字，空白不计。
    这样 ``chunk_size=300`` 表示"约 300 个汉字的信息量"，而不是"300 个字符"——
    否则一个 300 字符的纯英文段落（约 50 个单词）会被当成和 300 个汉字等量。

    Args:
        text: 待切分的原始文本。
        chunk_size: 每块的目标有效长度（字），必须为正数。
        overlap: 相邻块重叠的字符数，必须非负且小于 chunk_size。

    Returns:
        list[tuple[int, int]]: 按文本顺序排列的 (start, end) 半开区间，可直接
            用 text[start:end] 取出片段。遇到边界时优先选窗口内最靠后的双换行、
            单换行或中文句末标点；边界太靠前时退回硬切。

    Raises:
        ValueError: chunk_size 非正数、overlap 为负数或 overlap 不小于
            chunk_size 时抛出。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    spans: list[tuple[int, int]] = []
    start = 0
    text_length = len(text)
    budget_units = int(chunk_size) * _LATIN_PER_WORD
    while start < text_length:
        # 按有效长度推进窗口右端（汉字 1、英文 3 字母 = 1）
        end = _end_of_budget(text, start, budget_units)
        if end < text_length:
            # 按优先级找窗口内最靠后的完整边界，字符保留在前一块。
            boundary = text.rfind("\n\n", start, end)
            if boundary != -1:
                cut = boundary + 2
            else:
                boundary = text.rfind("\n", start, end)
                if boundary == -1:
                    boundary = max(
                        text.rfind(mark, start, end) for mark in "。！？；"
                    )
                cut = boundary + 1

            # 边界太靠前（不足目标的一半）时退回硬切，避免切出过碎的块
            if boundary != -1 and _units(text[start:cut]) * 2 >= budget_units:
                end = cut

        spans.append((start, end))
        if end >= text_length:
            break
        start = max(end - overlap, start + 1)
    return spans
