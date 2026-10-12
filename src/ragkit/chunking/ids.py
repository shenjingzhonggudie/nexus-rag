def make_chunk_id(doc_id: str, text: str, occurrence: int) -> str:
    """按文档标识、文本指纹和出现序号构造片段 ID。

    Args:
        doc_id: 片段所属文档的标识。
        text: 用于计算 SHA-256 指纹的片段文本。
        occurrence: 同一文档内相同文本片段的出现序号，从 1 开始。

    Returns:
        str: 格式为 ``{doc_id}#{sha256(text)前8位}@{occurrence}`` 的 ID。

    Raises:
        ValueError: occurrence 小于 1 时抛出。
    """
    if occurrence < 1:
        raise ValueError("occurrence must be >= 1")

    from hashlib import sha256

    return f"{doc_id}#{sha256(text.encode('utf-8')).hexdigest()[:8]}@{occurrence}"