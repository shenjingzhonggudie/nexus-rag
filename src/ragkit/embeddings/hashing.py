"""基于哈希技巧（feature hashing）的文本嵌入，无需训练、结果可复现。"""

from hashlib import sha256
from ragkit.text import tokenize


def embed_text(text: str, *, dim: int) -> list[float]:
    """把文本转换为 dim 维、经 L2 归一化的向量。

    步骤：分词 -> 对每个 token 做 SHA-256 -> 映射到某一维并累加 ±1
    -> L2 归一化。相同文本的结果始终一致。

    Args:
        text: 输入文本。
        dim: 向量维度，必须大于 0。

    Returns:
        长度为 dim 的浮点列表；若文本没有任何 token，返回全零向量。

    Raises:
        ValueError: dim 不大于 0 时抛出。
    """
    if dim <= 0:
        raise ValueError("dim must be > 0")
    # 初始化全零向量，用来累计各维度的词频
    vec = [0.0] * dim
    # 保留重复的 token，重复出现的词会多次累加，即体现词频
    for token in tokenize(text):
        # 对 token 本身哈希（而不是整段文本），得到 32 字节摘要
        h = sha256(token.encode("utf-8")).digest()
        # 前 4 字节按大端转成整数，再对 dim 取模，决定落在哪一维
        idx = int.from_bytes(h[:4], "big") % dim
        # 第 5 字节的最低位决定符号，使不同 token 碰撞时可以部分抵消
        sign = 1 if (h[4] & 1) == 0 else -1
        vec[idx] += sign
    # L2 范数：各分量平方和的平方根
    norm = (sum(v * v for v in vec)) ** 0.5
    # 没有 token（或恰好全部抵消）时范数为 0，直接返回全零向量，避免除以 0
    if norm == 0.0:
        return vec
    # 归一化后向量长度为 1，便于直接用点积计算余弦相似度
    return [v / norm for v in vec]