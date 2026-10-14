"""目录加载：递归扫描目录，批量读取受支持的文件。"""

from pathlib import Path

from ragkit.errors import LoadError
from ragkit.schemas import Document

from .files import load_file
from .report import LoadFailure, LoadReport


def load_dir(
    root: Path,
    *,
    suffixes: tuple[str, ...] = (".txt", ".md", ".markdown"),
) -> LoadReport:
    """递归加载目录中的受支持文件，并以报告形式返回成功和失败结果。

    Args:
        root: 要递归扫描的根目录。
        suffixes: 允许加载的文件扩展名；匹配时不区分大小写。

    Returns:
        LoadReport: 成功文档按相对 POSIX source 路径排序；失败文件记入 failures，
            单个文件加载失败不会中断整批处理。

    Raises:
        FileNotFoundError: root 不存在或不是目录时抛出。
    """

    if not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")

    allowed = {s.lower() for s in suffixes}
    # source 用相对 root 的 POSIX 路径，保证跨平台可复现。
    candidates: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        # 只检查相对路径，root 自身位于隐藏目录下时不应被跳过。
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.is_file() and path.suffix.lower() in allowed:
            candidates.append((relative.as_posix(), path))
    candidates.sort(key=lambda item: item[0])

    documents: list[Document] = []
    failures: list[LoadFailure] = []
    for source, path in candidates:
        try:
            documents.append(load_file(path, source=source))
        except LoadError as e:
            # e.path 是调用方传入的完整路径，属"人类定位"坐标系；
            # LoadFailure 要进报告与 manifest，必须换成本层的 source 坐标系。
            failures.append(LoadFailure(path=source, reason=e.reason, error_type=e.error_type))

    return LoadReport(documents=documents, failures=failures)