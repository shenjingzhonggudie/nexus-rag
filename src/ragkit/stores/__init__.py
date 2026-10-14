"""向量存储子包：提供向量库的写入、读取与内存表示。"""

from .vector_store import VectorStore, load, write

__all__ = ["VectorStore", "load", "write"]
