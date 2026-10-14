"""向量库的内存表示，以及向量库在磁盘上的写入与读取。"""

from dataclasses import dataclass
import os
import json
from pathlib import Path

import numpy as np

from ragkit.errors import StoreCorruptError

@dataclass
class VectorStore:
    """内存中的向量库，三个字段按下标一一对应。

    Attributes:
        ids: 每个 chunk 的唯一标识。
        matrix: 向量矩阵，float32，形状为 (N, dim)，每行是一个 chunk 的向量。
        metadata: 每个 chunk 的附加信息，如来源和位置。
    """

    ids: list[str]          # 每个 chunk 的唯一标识
    matrix: np.ndarray      # float32, shape (N, dim)，每行是一个 chunk 的向量
    metadata: list[dict]    # 每个 chunk 的附加信息（如来源、位置）

    @property
    def dim(self) -> int:
        """向量维度，即矩阵的列数。"""
        return self.matrix.shape[1]

    def __len__(self) -> int:
        """库中向量（chunk）的数量。"""
        return len(self.ids)


def write(directory: Path, *, dim: int, ids: list[str], vectors: list[list[float]], metadata: list[dict]) -> None:
    """把向量、ids 和 metadata 写入目录，最后写 manifest 作为提交点。

    Args:
        directory: 输出目录，不存在时自动创建。
        dim: 每个向量的维度，必须大于 0。
        ids: 每个 chunk 的唯一标识，与 vectors、metadata 按下标对应。
        vectors: 每个 chunk 的向量，每个向量长度都必须等于 dim。
        metadata: 每个 chunk 的附加信息，长度必须与 ids 相同。

    Returns:
        None: 全部文件写入完成后返回。

    Raises:
        ValueError: dim 不是正数、三个列表长度不一致、ids 有重复，或某个向量长度不等于 dim 时抛出。
    """
    if dim <= 0:
        raise ValueError("dim must be > 0")
    if len(ids) != len(vectors) or len(ids) != len(metadata):
        raise ValueError("ids, vectors, and metadata must have the same length")
    if len(set(ids)) != len(ids):
        raise ValueError("ids must be unique")
    for vec in vectors:
        if len(vec) != dim:
            raise ValueError(f"Each vector must have length {dim}")
    os.makedirs(directory, exist_ok=True)
    d = Path(directory)

    # 1) 先写临时文件
    tmp_vectors = d / "vectors.tmp.npy"
    tmp_ids     = d / "ids.json.tmp"
    tmp_meta    = d / "metadata.json.tmp"

    np.save(tmp_vectors, np.array(vectors, dtype=np.float32).reshape(-1, dim))
    with open(tmp_ids, "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, indent=2)
    with open(tmp_meta, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # 2) 全部成功后，逐个原子替换
    os.replace(tmp_vectors, d / "vectors.npy")
    os.replace(tmp_ids,     d / "ids.json")
    os.replace(tmp_meta,    d / "metadata.json")

    # 3) 最后写 manifest（提交点）
    with open(d / "manifest.json", "w", encoding="utf-8") as f:
        json.dump({"version": 1, "dim": dim,
                   "count": len(ids)}, f, ensure_ascii=False, indent=2)


def load(directory: Path) -> VectorStore:
    """从 write 生成的目录读取向量库，并校验 manifest、维度和行数是否一致。

    Args:
        directory: 向量库所在目录。

    Returns:
        VectorStore: 读取到的向量库，matrix 为 float32 数组。

    Raises:
        StoreCorruptError: manifest 缺失或非法、向量维度与 manifest 不符，或行数不一致时抛出。
        FileNotFoundError: vectors.npy、ids.json 或 metadata.json 缺失时抛出。
    """
    d = Path(directory)

    # 1) manifest 是提交点，必须先读它；缺失或格式非法都视为损坏
    try:
        with open(d / "manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
        expected_dim = manifest["dim"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise StoreCorruptError(f"{d}: manifest.json is missing or invalid") from e

    try:
        vectors = np.load(d / "vectors.npy")
        with open(d / "ids.json", "r", encoding="utf-8") as f:
            ids = json.load(f)
        with open(d / "metadata.json", "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except FileNotFoundError:
        # 文件缺失按文档约定保持 FileNotFoundError，不归为损坏
        raise
    except (OSError, ValueError) as e:
        raise StoreCorruptError(f"{d}: vectors, ids, or metadata file is unreadable") from e

    # 2) 维度必须与 manifest 一致
    if vectors.ndim != 2 or vectors.shape[1] != expected_dim:
        raise StoreCorruptError(
            f"{d}: vector shape {vectors.shape} does not match manifest dim {expected_dim}"
        )

    # 3) 向量、ids、metadata 的行数必须全部相同
    if not (vectors.shape[0] == len(ids) == len(metadata)):
        raise StoreCorruptError(
            f"{d}: row counts differ (vectors={vectors.shape[0]}, "
            f"ids={len(ids)}, metadata={len(metadata)})"
        )

    return VectorStore(ids=ids, matrix=vectors, metadata=metadata)