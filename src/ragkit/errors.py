class RagkitError(Exception):
    """所有领域异常的共同基类，方便调用方一次捕获"""

class ConfigError(RagkitError):
    """配置内容非法（不继承 ValueError，避免和别的 ValueError 混在一起）"""


#情况	抛什么
#路径写错 / 文件不存在	标准异常 FileNotFoundError
#文件内容不对	领域异常 ConfigError
#Pydantic 校验失败	ValidationError 包装成 ConfigError（用 raise ... from exc 保留原始堆栈）
