"""chunks.jsonl 的写入与读取：索引里每个块一行，供查询侧还原 id_to_chunk。

格式契约（第 14 轮拍板，改动即破坏性变更）：
- 每行一个 `Chunk.to_dict()` 的 JSON 对象，UTF-8，行间以换行分隔；
- 与 stores 的"整个 JSON 数组"取舍相反：chunks 面向增量追加（下一轮增量
  更新时坏一行只损一块），stores 当时的判断是"阶段 8 反正要重写矩阵"。
"""

import json
import os
from pathlib import Path

from ragkit.schemas import Chunk


def write_chunks(path: Path, chunks: list[Chunk]) -> None:
    """把块列表写成 JSONL，先写临时文件再原子替换（与 stores 同款策略）。

    Args:
        path: 目标文件路径，通常为 index_dir / "chunks.jsonl"。
        chunks: 待落盘的块；空列表会写出空文件（空语料是合法产物）。

    Returns:
        None: 全部行写入并替换完成后返回。

    Raises:
        OSError: 目录不存在或磁盘不可写时由 open 抛出。
    """
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def read_chunks(path: Path) -> list[Chunk]:
    """读取 JSONL 并还原为 Chunk 列表。

    Args:
        path: chunks.jsonl 路径；空行跳过（文件末尾换行不视为数据）。

    Returns:
        list[Chunk]: 逐行 Chunk.from_dict 的结果；空文件返回空列表。

    Raises:
        FileNotFoundError: 文件不存在时由 open 抛出（与 stores.load 的
            "缺失按缺失、损坏按损坏"口径一致）。
        ValueError: 某行不是合法 JSON、或缺少 Chunk 必填字段时抛出，
            消息带上行号与原因，方便定位坏行。
    """
    chunks: list[Chunk] = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(Chunk.from_dict(json.loads(line)))
            except ValueError as e:
                raise ValueError(f"{path}:{lineno}: 无法解析为 Chunk（{e}）") from e
    return chunks
