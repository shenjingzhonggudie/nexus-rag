"""本地 BGE 语义嵌入（需 sentence-transformers）。

与 hashing 实现保持同一契约：``embed_text(text, *, dim) -> list[float]``，
返回 L2 归一化向量，使下游点积即余弦相似度。

模型懒加载并缓存：首次调用时加载（离线环境需提前把模型下载到本地，或用
本地路径作 model_name），之后的调用复用同一个模型实例。
"""

from typing import Any

# 模型缓存：model_name -> SentenceTransformer 实例（避免重复加载）
_model_cache: dict[str, Any] = {}

DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"  # 512 维，中文，体积较小


def embed_text(
    text: str, *, dim: int, model_name: str = DEFAULT_MODEL_NAME
) -> list[float]:
    """用本地 BGE 模型把文本转换为 dim 维、L2 归一化的向量。

    Args:
        text: 输入文本；空文本返回全零向量（与 hashing 的边界行为一致）。
        dim: 期望的向量维度，必须与模型输出维度一致（bge-small-zh-v1.5 为 512）。
        model_name: HuggingFace 模型名或本地模型目录；默认 bge-small-zh-v1.5。

    Returns:
        list[float]: 长度为 dim 的归一化向量。

    Raises:
        ValueError: dim 不是正数，或模型实际输出维度与 dim 不一致时抛出。
        ImportError: 未安装 sentence-transformers 时抛出。
    """
    if dim <= 0:
        raise ValueError("dim must be > 0")
    # 空文本没有语义，直接给全零向量（避免模型对空串返回非零或报错）
    if not text.strip():
        return [0.0] * dim

    model = _load_model(model_name)
    # normalize_embeddings=True：输出 L2 归一化，下游点积即余弦
    vector = model.encode(text, normalize_embeddings=True)
    result = [float(x) for x in vector.tolist()]

    if len(result) != dim:
        raise ValueError(
            f"模型 {model_name} 输出维度 {len(result)} 与配置 embedding.dim={dim} 不一致；"
            f"请把 embedding.dim 改成 {len(result)}"
        )
    return result


def _load_model(model_name: str) -> Any:
    """加载并缓存模型（同一模型只加载一次）。

    Args:
        model_name: HuggingFace 模型名或本地模型目录。

    Returns:
        Any: SentenceTransformer 实例。

    Raises:
        ImportError: 未安装 sentence-transformers 时抛出（附安装提示）。
    """
    if model_name in _model_cache:
        return _model_cache[model_name]
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的提示分支
        raise ImportError(
            "接入 BGE 需要安装 sentence-transformers：\n"
            '  pip install "sentence-transformers"\n'
            '或安装可选依赖组：pip install -e ".[embedding]"'
        ) from exc
    _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]
