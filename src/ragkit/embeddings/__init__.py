"""嵌入（embedding）模块：把文本转换为固定维度的数值向量。"""

from .hashing import embed_text

# 对外只暴露 embed_text，内部实现细节留在 hashing 模块中
__all__ = ["embed_text"]