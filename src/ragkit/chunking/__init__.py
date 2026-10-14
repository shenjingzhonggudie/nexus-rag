"""文本切分：把文档切分为带稳定 ID 和字符偏移的片段。"""

from .document import chunk_document, iter_spans, make_chunk_id
from .fixed import iter_spans
from .ids import make_chunk_id


__all__ = ["chunk_document", "iter_spans", "make_chunk_id"]