from hashlib import sha256
from ragkit.text import tokenize

def embed_text(text: str, *, dim: int) -> list[float]:
    if dim <= 0:
        raise ValueError("dim must be > 0")
    vec = [0.0] * dim
    for token in tokenize(text):              # ← 双通道、保留重复：这就是词频
        h = sha256(token.encode("utf-8")).digest()   # ← 对 token 哈希，不是对 text
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1 if (h[4] & 1) == 0 else -1
        vec[idx] += sign                       # 出现一次加一次 → 累计词频
    norm = (sum(v * v for v in vec)) ** 0.5
    if norm == 0.0:
        return vec                             # 空 token → 全零（决策 B）
    return [v / norm for v in vec]             # 决策 A：L2 归一化