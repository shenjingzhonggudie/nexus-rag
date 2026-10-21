"""指标纯函数的契约测试：手算样例、去重、截断、边界（空/零答案/k 非法）。"""

import pytest

from ragkit.evaluation.metrics import coverage_recall, first_hit_mrr


def test_coverage_recall_hand_calculated():
    # 3 个答案小节：第 1 个结果覆盖 {0}，第 2 个覆盖 {1,2}
    hits = [{0}, {1, 2}, set()]

    assert coverage_recall(hits, total=3, k=1) == pytest.approx(1 / 3)
    assert coverage_recall(hits, total=3, k=2) == pytest.approx(1.0)
    assert coverage_recall(hits, total=3, k=3) == pytest.approx(1.0)


def test_coverage_recall_single_answer():
    # 最常见的单答案场景：命中即 1.0
    assert coverage_recall([set(), {0}], total=1, k=2) == pytest.approx(1.0)
    assert coverage_recall([set()], total=1, k=1) == 0.0


def test_coverage_recall_duplicate_hits_count_once():
    # 多个块命中同一个小节 → 只算一次覆盖（覆盖是集合运算，不是计数）
    hits = [{0}, {0}, {0}]
    assert coverage_recall(hits, total=1, k=3) == pytest.approx(1.0)
    assert coverage_recall(hits, total=2, k=3) == pytest.approx(0.5)


def test_coverage_recall_k_exceeds_length():
    # k 超出结果长度 → 按实际长度截断，分母仍是答案总数
    assert coverage_recall([{0}], total=2, k=10) == pytest.approx(0.5)


def test_coverage_recall_no_answers_returns_zero():
    # 无答案 query（total=0）不除零
    assert coverage_recall([{0}], total=0, k=5) == 0.0


def test_coverage_recall_empty_hits_returns_zero():
    assert coverage_recall([], total=2, k=3) == 0.0


def test_coverage_recall_nonpositive_k_raises():
    with pytest.raises(ValueError):
        coverage_recall([{0}], total=1, k=0)
    # k 非法是参数错误，即使 total 为 0 也优先报（参数校验最先）
    with pytest.raises(ValueError):
        coverage_recall([], total=0, k=-1)


def test_first_hit_mrr_hand_calculated():
    assert first_hit_mrr([{0}, set()]) == pytest.approx(1.0)      # rank 1
    assert first_hit_mrr([set(), set(), {1}]) == pytest.approx(1 / 3)  # rank 3


def test_first_hit_mrr_no_hit_returns_zero():
    assert first_hit_mrr([set(), set()]) == 0.0
    assert first_hit_mrr([]) == 0.0
