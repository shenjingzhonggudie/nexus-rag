"""固定长度切分的契约：长度单位是「字」，不是字符。

汉字 1 个字、英文字母 3 个算 1 个字、空白不计。所以同样的 ``chunk_size``，
纯中文文本切出的块和纯英文文本切出的块字符数差约 3 倍——测试必须按这个
前提写数据，否则会得到一堆看着像 bug、其实是单位换算的失败。
"""

from itertools import product

import pytest

from ragkit.chunking.fixed import effective_len, iter_spans


@pytest.mark.parametrize("text", ["", "甲乙丙"])
@pytest.mark.parametrize(
    "chunk_size, overlap", [(0, 0), (-1, 0), (4, -1), (4, 4), (4, 5)]
)
def test_invalid_parameters(text, chunk_size, overlap):
    with pytest.raises(ValueError):
        iter_spans(text, chunk_size=chunk_size, overlap=overlap)


# ---------- 长度单位 ----------


def test_effective_len_counts_latin_as_one_third():
    assert effective_len("abc") == pytest.approx(1.0)
    assert effective_len("甲乙丙") == pytest.approx(3.0)
    assert effective_len(" \n\t") == 0.0


def test_latin_text_needs_three_times_the_budget():
    # 12 个字母 = 4 个字：chunk_size=4 时正好一块
    assert iter_spans("abcdefghijkl", chunk_size=4, overlap=0) == [(0, 12)]
    # chunk_size=2 时切成两块，每块 6 字母 = 2 个字
    assert iter_spans("abcdefghijkl", chunk_size=2, overlap=0) == [(0, 6), (6, 12)]


def test_cjk_text_maps_one_char_to_one_word():
    # 12 个汉字 = 12 个字：chunk_size=4 时三块，硬切（无边界字符）
    assert iter_spans("甲乙丙丁戊己庚辛壬癸子丑", chunk_size=4, overlap=0) == [
        (0, 4),
        (4, 8),
        (8, 12),
    ]


# ---------- 边界选择 ----------


def test_double_newline_is_preferred():
    text = "甲乙\n\n丙丁戊己庚辛"
    spans = iter_spans(text, chunk_size=4, overlap=0)
    # 窗口覆盖到"丁"（4 字），双换行在位置 2，cut=4 且有效长度 2 >= 2 → 接受
    assert spans[0] == (0, 4)


def test_boundary_too_early_falls_back_to_hard_cut():
    # 双换行在开头（有效长度 0），不足目标的一半 → 不接受，退回硬切
    text = "\n\n甲乙丙丁戊己庚辛"
    spans = iter_spans(text, chunk_size=4, overlap=0)
    assert spans[0] == (0, 6)


def test_short_text_stays_in_one_span():
    for text in ("", "甲\n。", "甲\n。乙"):
        spans = iter_spans(text, chunk_size=4, overlap=3)
        if text:
            assert spans == [(0, len(text))]
        else:
            assert spans == []


# ---------- 重叠与不变量 ----------


def test_overlap_advances_by_one_char():
    assert iter_spans("甲乙丙丁戊己庚辛", chunk_size=2, overlap=1) == [
        (0, 2),
        (1, 3),
        (2, 4),
        (3, 5),
        (4, 6),
        (5, 7),
        (6, 8),
    ]


def test_offsets_preserve_original_text():
    text = "甲\r\n\u200b。乙"
    spans = iter_spans(text, chunk_size=10, overlap=0)
    assert "".join(text[start:end] for start, end in spans) == text


def test_span_invariants():
    """覆盖完整、无空洞、每块有效长度受控（允许 1 字边界溢出）。"""
    for length in range(6):
        for chars in product("甲\n。", repeat=length):
            text = "".join(chars)
            for chunk_size in range(1, 5):
                for overlap in range(chunk_size):
                    spans = iter_spans(text, chunk_size=chunk_size, overlap=overlap)
                    if not text:
                        assert spans == []
                        continue
                    assert spans[0][0] == 0
                    assert spans[-1][1] == len(text)
                    covered: set[int] = set()
                    for start, end in spans:
                        assert 0 <= start < end <= len(text)
                        # 边界可能跨过预算一点点，容忍 1 个字
                        assert effective_len(text[start:end]) <= chunk_size + 1
                        covered.update(range(start, end))
                    assert covered == set(range(len(text)))
                    for (start, end), (next_start, _) in zip(spans, spans[1:]):
                        assert next_start == max(end - overlap, start + 1)
