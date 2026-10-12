"""将文档正文规范化并切分为带有来源和偏移信息的片段。"""

from hashlib import sha256

from ragkit.schemas import Chunk, Document
from ragkit.text.normalize import normalize_text

from .fixed import iter_spans
from .ids import make_chunk_id


def chunk_document(
    document: Document, *, chunk_size: int = 400, overlap: int = 50
) -> list[Chunk]:
    """规范化并切分文档正文，生成带稳定标识和字符偏移的片段。

    切分对象是 ``normalize_text(document.text)``。偏移相对于规范化后的文本，
    且正文不执行 strip，以保证 ``chunk.text == normalized[char_start:char_end]``。
    每个片段的 metadata 恰含 strategy、char_start、char_end、content_hash 四键。
    重复片段以完整 SHA-256 值计数，ID 展示哈希时才截取前 8 位。

    Args:
        document: 要切分的文档；生成的片段继承其 doc_id、source 和 title。
        chunk_size: 每块的最大目标字符数，默认 400，必须为正数。
        overlap: 相邻块重叠的字符数，默认 50，必须非负且小于 chunk_size。

    Returns:
        list[Chunk]: 按切片顺序生成的片段。ordinal 从 0 开始连续递增；metadata
            中的 content_hash 是 chunk.text 的 SHA-256 十六进制摘要前 16 位。
            空正文返回空列表。

    Raises:
        ValueError: chunk_size 非正数、overlap 为负数或 overlap 不小于
            chunk_size 时抛出。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")

    normalized = normalize_text(document.text)
    spans = iter_spans(normalized, chunk_size=chunk_size, overlap=overlap)
    occurrences: dict[str, int] = {}
    chunks: list[Chunk] = []

    for ordinal, (char_start, char_end) in enumerate(spans):
        chunk_text = normalized[char_start:char_end]
        full_hash = sha256(chunk_text.encode("utf-8")).hexdigest()
        occurrence = occurrences.get(full_hash, 0) + 1
        occurrences[full_hash] = occurrence

        chunks.append(
            Chunk(
                chunk_id=make_chunk_id(document.doc_id, chunk_text, occurrence),
                doc_id=document.doc_id,
                text=chunk_text,
                ordinal=ordinal,
                title=document.title,
                source=document.source,
                metadata={
                    "strategy": "fixed",
                    "char_start": char_start,
                    "char_end": char_end,
                    "content_hash": full_hash[:16],
                },
            )
        )

    return chunks
