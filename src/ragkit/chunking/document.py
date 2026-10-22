"""将文档正文规范化并切分为带有来源和偏移信息的片段。"""

from hashlib import sha256

from ragkit.schemas import Chunk, Document
from ragkit.text.normalize import normalize_text

from .fixed import effective_len, iter_spans
from .heading import iter_heading_spans
from .ids import make_chunk_id

# 有效长度低于此值的块直接丢弃：典型是 MDX 组件闭合标签、代码块结尾、
# 注释残骸——字符数看着不少（13~40），但信息量只有 3~15 字，没有检索价值。
_MIN_CHUNK_LEN = 10


def chunk_document(
    document: Document,
    *,
    strategy: str = "fixed",
    chunk_size: int = 300,
    overlap: int = 50,
) -> list[Chunk]:
    """规范化并切分文档正文，生成带稳定标识和字符偏移的片段。

    切分对象是 ``normalize_text(document.text)``。偏移相对于规范化后的文本，
    且正文不执行 strip，以保证 ``chunk.text == normalized[char_start:char_end]``。
    每个片段的 metadata 恰含 strategy、char_start、char_end、content_hash 四键。
    重复片段以完整 SHA-256 值计数，ID 展示哈希时才截取前 8 位。

    Args:
        document: 要切分的文档；生成的片段继承其 doc_id、source 和 title。
        strategy: 切分策略。"fixed" 按目标长度与重叠量切分；"heading" 按
            Markdown 二级标题（##）切分，每个小节一个片段（块级标注用）。
        chunk_size: 每块的最大目标字符数，默认 300，仅 fixed 策略生效。
        overlap: 相邻块重叠的字符数，默认 50，仅 fixed 策略生效。

    Returns:
        list[Chunk]: 按切片顺序生成的片段。ordinal 从 0 开始连续递增；metadata
            中的 content_hash 是 chunk.text 的 SHA-256 十六进制摘要前 16 位。
            空正文返回空列表。

    Raises:
        ValueError: fixed 策略下 chunk_size 非正数、overlap 为负数或 overlap
            不小于 chunk_size 时抛出。
    """
    normalized = normalize_text(document.text)

    if strategy == "heading":
        spans = iter_heading_spans(normalized)
        meta_strategy = "heading"
    else:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if overlap < 0:
            raise ValueError("overlap must be >= 0")
        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size")
        spans = iter_spans(normalized, chunk_size=chunk_size, overlap=overlap)
        meta_strategy = "fixed"
    occurrences: dict[str, int] = {}
    chunks: list[Chunk] = []

    for char_start, char_end in spans:
        chunk_text = normalized[char_start:char_end]
        # 质量闸门：有效长度低于 10 字的块直接丢弃。
        # 典型来源是 MDX 组件闭合标签（`</Sandpack>`）、代码块结尾（`;\n```）、
        # 被剥掉的注释残骸（`## Metrics\n-->`）——它们字符数看着不少，但没有任何
        # 检索价值，留着只会污染候选池（实测 18 个，最短 2 字符）。
        if effective_len(chunk_text) < _MIN_CHUNK_LEN:
            continue
        ordinal = len(chunks)  # 过滤后重新连续编号，避免跳号
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
                    "strategy": meta_strategy,
                    "char_start": char_start,
                    "char_end": char_end,
                    "content_hash": full_hash[:16],
                },
            )
        )

    return chunks
