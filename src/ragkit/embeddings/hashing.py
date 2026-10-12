def embed_text(text: str, *, dim: int) -> list[float]:
    import hashlib

    hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
    hash_ints = [b for b in hash_bytes]
    embedding = [(hash_ints[i % len(hash_ints)] / 255.0) for i in range(dim)]
    return embedding