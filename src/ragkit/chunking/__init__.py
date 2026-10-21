"""文本切分：把文档切分为带稳定 ID 和字符偏移的片段。"""

from .document import chunk_document
from .fixed import iter_spans
from .heading import iter_heading_sections, iter_heading_spans
from .ids import make_chunk_id


__all__ = [
    "chunk_document",
    "iter_spans",
    "iter_heading_sections",
    "iter_heading_spans",
    "make_chunk_id",
]