"""嵌入（embedding）模块：把文本转换为固定维度的数值向量。

两种实现：
- ``hashing``：基于哈希技巧的字面级向量（默认，零依赖、离线可用、可复现）；
- ``bge``：本地 BGE 语义模型（需 sentence-transformers，见 ``bge.py``）。

通过 ``configure()`` 在 build / load_index 时切一次实现，之后所有
``embed_text`` 调用（文档向量、query 向量、精排向量）都走同一个模型——
这是检索正确的前提：**文档和 query 必须落在同一个语义空间**。
"""

from .hashing import embed_text as _hashing_embed_text

_provider: str = "hashing"
_model_name: str = ""


def configure(*, provider: str = "hashing", model_name: str = "") -> None:
    """设置全局 embedding 实现（build 与 load_index 时各调用一次）。

    Args:
        provider: ``"hashing"`` 或 ``"bge"``。
        model_name: bge 的模型名/本地路径；hashing 忽略。
    """
    global _provider, _model_name
    _provider = provider
    _model_name = model_name


def embed_text(text: str, *, dim: int) -> list[float]:
    """把文本转换为 dim 维、L2 归一化的向量（实现由 ``configure`` 决定）。

    Args:
        text: 输入文本。
        dim: 向量维度，必须大于 0；bge 时还必须与模型输出维度一致。

    Returns:
        list[float]: 长度为 dim 的归一化向量；无 token / 空文本返回全零向量。

    Raises:
        ValueError: dim 不大于 0，或 bge 模型输出维度与 dim 不一致时抛出。
        ImportError: provider 为 bge 且未安装 sentence-transformers 时抛出。
    """
    if _provider == "bge":
        from .bge import embed_text as _bge_embed_text

        return _bge_embed_text(text, dim=dim, model_name=_model_name)
    return _hashing_embed_text(text, dim=dim)


__all__ = ["embed_text", "configure"]
