class RagkitError(Exception):
    """所有 RAGKit 领域异常的共同基类。

    直接捕获该异常可统一处理本项目主动报告的领域错误。
    """


class ConfigError(RagkitError):
    """表示配置文件内容或合并后的配置不合法。

    单独继承 RagkitError 而非 ValueError，避免与其他值校验错误混淆。
    """


class LoadError(RagkitError):
    """单个文件加载失败。

    Attributes:
        path: 调用方传入的路径原样保留，供人类定位（可能包含机器相关的目录）。
            需要跨机器复现的场合（报告、manifest）请换用相对 source 坐标系。
        reason: 可直接展示给人看的失败原因。
        error_type: 原始异常类名，供机器分类统计。
    """

    def __init__(self, path: str, reason: str, error_type: str) -> None:
        """构造单文件加载异常。

        Args:
            path: 调用方提供的路径字符串，用于定位文件。
            reason: 可供人阅读的失败原因。
            error_type: 原始异常的类名，供机器分类统计。

        Returns:
            None: 初始化异常消息及 path、reason、error_type 属性。
        """
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason
        self.error_type = error_type
