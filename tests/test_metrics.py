"""指标纯函数的契约测试：手算样例、截断、边界（空/越界/k 非法）。"""

import pytest

from ragkit.evaluation.metrics import mrr, recall_at_k

REL = {"a.txt", "b.txt"}


def test_recall_hand_calculated():
    r = ["a.txt", "c.txt", "b.txt", "d.txt"]

    assert recall_at_k(r, REL, k=2) == pytest.approx(0.5)   # [a,c] 命中 1 / 2
    assert recall_at_k(r, REL, k=3) == pytest.approx(1.0)   # [a,c,b] 命中 2 / 2
    assert recall_at_k(r, REL, k=1) == pytest.approx(0.5)   # [a] 命中 1 / 2


def test_recall_k_exceeds_length():
    # k 超出检索长度 → 按实际长度截断，分母仍是相关总数
    assert recall_at_k(["a.txt"], REL, k=10) == pytest.approx(0.5)


def test_recall_empty_relevant_returns_zero():
    assert recall_at_k(["a.txt", "b.txt"], set(), k=2) == 0.0


def test_recall_empty_retrieved_returns_zero():
    assert recall_at_k([], REL, k=3) == 0.0


def test_recall_nonpositive_k_raises():
    with pytest.raises(ValueError):
        recall_at_k(["a.txt"], REL, k=0)
    # k 非法是参数错误，即使 relevant 也空也优先报（参数校验最先）
    with pytest.raises(ValueError):
        recall_at_k([], set(), k=-1)


def test_mrr_hand_calculated():
    assert mrr(["a.txt", "c.txt", "b.txt"], REL) == pytest.approx(1.0)  # rank 1
    assert mrr(["c.txt", "d.txt", "a.txt"], REL) == pytest.approx(1 / 3)  # rank 3


def test_mrr_no_hit_returns_zero():
    assert mrr(["c.txt", "d.txt"], REL) == 0.0


def test_mrr_empty_relevant_returns_zero():
    assert mrr(["a.txt"], set()) == 0.0
