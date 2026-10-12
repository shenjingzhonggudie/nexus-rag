"""Hashing Embedding 的契约测试。

覆盖决策 A~E 与一个关键陷阱：
- 长度恒为 dim、非空 token 时范数 = 1（决策 A）；
- 相似度按 token 重叠排序（决策 C/D 的语义正确性）；
- 空 token → 全零（决策 B）；
- 跨进程稳定（抓"误用内置 hash()"——hash() 受 PYTHONHASHSEED 随机化）。
"""

import os
import subprocess
import sys
from math import sqrt

import pytest

from ragkit.embeddings import embed_text


def _cos(a: list[float], b: list[float]) -> float:
    # 两个向量都已 L2 归一化，点积即余弦。
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return sqrt(sum(x * x for x in a))


@pytest.mark.parametrize("dim", [8, 64, 512, 1024])
def test_vector_length_equals_dim(dim):
    assert len(embed_text("容器冷启动", dim=dim)) == dim


@pytest.mark.parametrize("text", ["容器冷启动", "hello world", "容器 cold 启动 v1.2"])
def test_vector_is_unit_length_for_nonempty_tokens(text):
    assert _norm(embed_text(text, dim=128)) == pytest.approx(1.0)


def test_embedding_is_deterministic():
    assert embed_text("容器冷启动", dim=64) == embed_text("容器冷启动", dim=64)


def test_vector_is_stable_across_processes():
    # 内置 hash() 受 PYTHONHASHSEED 影响，sha256 不受。两个子进程用不同种子，
    # 输出必须逐字相同 —— 证明实现用的是加密哈希而非 hash()。
    code = (
        "from ragkit.embeddings import embed_text; "
        "print(embed_text('\\u5bb9\\u5668\\u51b7\\u542f\\u52a8', dim=32))"
    )
    outputs = []
    for seed in ("0", "12345"):
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        assert proc.returncode == 0, proc.stderr
        outputs.append(proc.stdout)
    assert outputs[0] == outputs[1]


def test_similarity_orders_by_token_overlap():
    identical = embed_text("容器冷启动", dim=256)
    same_tokens = embed_text("容器冷启动。", dim=256)  # 句号被过滤 → 向量完全相同
    overlapping = embed_text("容器冷启动耗时长", dim=256)  # 共享大部分词
    unrelated = embed_text("数据库连接池", dim=256)

    assert _cos(identical, same_tokens) == pytest.approx(1.0)
    assert _cos(identical, same_tokens) > _cos(identical, overlapping)
    assert _cos(identical, overlapping) > _cos(identical, unrelated)


@pytest.mark.parametrize("text", ["", "。，！？"])
def test_empty_tokens_yield_zero_vector(text):
    assert embed_text(text, dim=16) == [0.0] * 16


@pytest.mark.parametrize("dim", [0, -1])
def test_non_positive_dim_raises(dim):
    with pytest.raises(ValueError):
        embed_text("容器", dim=dim)
