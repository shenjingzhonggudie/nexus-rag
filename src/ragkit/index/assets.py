"""建库产物的内存容器：把 search 的四个散参数打包，调用方不可能错位。"""

from dataclasses import dataclass, field

from ragkit.loaders import LoadFailure
from ragkit.retrieval import BM25Index
from ragkit.schemas import Chunk
from ragkit.stores import VectorStore


@dataclass
class BuiltIndex:
    """一次建库（或索引加载）得到的"检索就绪资源"。

    Attributes:
        bm25: 内存 BM25 索引（统计由本次分块结果或落盘 chunks 重建）。
        store: 向量库（内存表示，ids / matrix / metadata 三元组同序）。
        id_to_chunk: chunk_id 到块对象的映射，dense / rerank 靠它还原块。
        dim: 向量维度；build 时来自 cfg.embedding.dim，load 时来自 store.dim。
        failures: 建库时被隔离的坏文件（LoadReport.failures 的搬运），
            全部成功时为空列表；查询侧不关心它，调用方需要时可检查。
    """

    bm25: BM25Index
    store: VectorStore
    id_to_chunk: dict[str, Chunk]
    dim: int
    failures: list[LoadFailure] = field(default_factory=list)
