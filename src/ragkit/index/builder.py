"""建库与索引加载的编排：load → chunk → embed → 落盘 → BM25。"""

from pathlib import Path

import numpy as np

from ragkit.chunking import chunk_document
from ragkit.config import AppConfig
from ragkit.embeddings import embed_text
from ragkit.index.assets import BuiltIndex
from ragkit.index.chunks_store import read_chunks, write_chunks
from ragkit.loaders import load_dir
from ragkit.retrieval import BM25Index
from ragkit.stores import VectorStore, load, write


def build(root: Path, cfg: AppConfig) -> BuiltIndex:
    """从原始文档目录建库：切块、向量化、落盘，并返回可直接检索的资源。

    Args:
        root: 待索引的文档根目录。
        cfg: 应用配置，提供切块参数、向量维度和索引输出目录。

    Returns:
        BuiltIndex: 内存中的 BM25、向量库、块映射；坏文件记录在 failures 中。
    """
    # 坏文件只进 failures，不会中断整批加载
    loaded_report = load_dir(root)
    # ids / vectors / metadata 三者按下标对应，all_chunks 保存完整块
    ids = []
    vectors = []
    metadata = []
    all_chunks = []
    for doc in loaded_report.documents:
        chunks = chunk_document(
            doc,
            strategy=cfg.chunking.strategy,
            chunk_size=cfg.chunking.chunk_size,
            overlap=cfg.chunking.overlap,
        )
        for chunk in chunks:
            vector = embed_text(chunk.text, dim=cfg.embedding.dim)
            ids.append(chunk.chunk_id)
            vectors.append(vector)
            metadata.append(chunk.metadata)
        all_chunks.extend(chunks)
    # write 会创建 index_dir，所以必须先于 write_chunks 调用
    write(cfg.index_dir, dim=cfg.embedding.dim, ids=ids, vectors=vectors, metadata=metadata)
    write_chunks(cfg.index_dir / "chunks.jsonl", all_chunks)
    # 以下直接用本次结果构造内存对象，不重新读盘
    bm25_index = BM25Index(all_chunks)
    # reshape 保证空语料时矩阵形状仍是 (0, dim)
    store = VectorStore(
        ids=ids,
        matrix=np.array(vectors, dtype=np.float32).reshape(-1, cfg.embedding.dim),
        metadata=metadata,
    )
    return BuiltIndex(bm25=bm25_index,
                      store=store,
                      id_to_chunk={chunk.chunk_id: chunk for chunk in all_chunks},
                      dim=cfg.embedding.dim,
                      failures=loaded_report.failures)


def load_index(index_dir: Path) -> BuiltIndex:
    """从 build 写出的索引目录加载检索资源，无需原始文档和配置。

    Args:
        index_dir: 包含向量库文件和 chunks.jsonl 的索引目录。

    Returns:
        BuiltIndex: 加载得到的检索资源；建库时的坏文件信息不落盘，failures 为空。
    """
    # 先读 manifest，自带维度与行数校验
    store = load(index_dir)
    chunks = read_chunks(index_dir / "chunks.jsonl")
    # 硬不变式：两份落盘文件的 chunk_id 必须一致，否则说明索引是半成品
    chunk_ids = {chunk.chunk_id for chunk in chunks}
    if chunk_ids != set(store.ids):
        raise ValueError(
            f"chunks.jsonl 有 {len(chunk_ids)} 个块，向量库有 {len(store.ids)} 个 id，两者不一致"
        )
    # BM25 统计不落盘，每次从 chunks 重建（第 14 轮决策 2：可再生的数据，重建优于落盘）
    bm25_index = BM25Index(chunks)
    return BuiltIndex(
        bm25=bm25_index,
        store=store,
        id_to_chunk={chunk.chunk_id: chunk for chunk in chunks},
        dim=store.dim,
        failures=[],
    )
