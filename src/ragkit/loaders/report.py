from dataclasses import dataclass, field

from ragkit.schemas import Document


@dataclass
class LoadFailure:
    """记录批量加载过程中一个文件的失败信息。

    Attributes:
        path: 失败文件的来源路径，批量加载时相对 root 且使用 POSIX 分隔符。
        reason: 可读的失败原因。
        error_type: 原始异常类名，用于分类统计。
    """

    path: str  # 失败文件的来源路径。
    reason: str  # 可读的失败原因。
    error_type: str  # 原始异常类名。


@dataclass
class LoadReport:
    """保存一次批量加载得到的文档和失败记录。

    Attributes:
        documents: 成功加载的文档，按加载器规定的顺序排列。
        failures: 加载失败的文件记录；单个失败不会阻止其余文件加载。
    """

    documents: list[Document] = field(default_factory=list)  # 成功加载的文档。
    failures: list[LoadFailure] = field(default_factory=list)  # 加载失败记录。