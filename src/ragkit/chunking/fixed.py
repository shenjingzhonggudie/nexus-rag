def iter_spans(text: str, *, chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    """按目标长度和重叠量生成文本的半开切片区间，不规范化文本。

    Args:
        text: 待切分的原始文本。
        chunk_size: 每块的最大字符数，必须为正数。
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
    while start < text_length:
        end = min(start + chunk_size, text_length)
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

            if boundary != -1 and cut >= start + chunk_size // 2:
                end = cut

        spans.append((start, end))
        if end >= text_length:
            break
        start = max(end - overlap, start + 1)
    return spans
