from itertools import product

import pytest

from ragkit.chunking.fixed import iter_spans


@pytest.mark.parametrize("text", ["", "abc"])
@pytest.mark.parametrize("chunk_size, overlap", [(0, 0), (-1, 0), (4, -1), (4, 4), (4, 5)])
def test_invalid_parameters(text, chunk_size, overlap):
    with pytest.raises(ValueError):
        iter_spans(text, chunk_size=chunk_size, overlap=overlap)


@pytest.mark.parametrize(
    "text, expected", [("", []), ("a\n。", [(0, 3)]), ("a\n。b", [(0, 4)])]
)
def test_empty_and_short_text(text, expected):
    assert iter_spans(text, chunk_size=4, overlap=3) == expected


@pytest.mark.parametrize(
    "text, chunk_size, expected_end",
    [
        ("abcd\n\nx\n。xyz", 10, 6),  # 双换行优先于更靠后的单换行和标点。
        ("abcd\nx。yz", 8, 5),
        ("ab\n\ncd\n\nefghij", 10, 8),  # 同级选最后一个。
        ("abc\nx\nyzzz", 8, 6),
        ("abc。d！e？f；gh", 10, 10),
        ("abc；d？e！f。gh", 10, 10),  # 标点之间没有优先级。
        ("abc。defgh", 8, 4),  # 恰好在回退下限也接受。
        ("ab。defghi", 8, 8),
        ("\n\nabc。defgh", 8, 8),  # 最高优先级边界过早时硬切。
        ("abcdefg\n\nxyz", 8, 8),  # 不读取窗口外的边界字符。
        ("abcdefghijk", 8, 8),
    ],
)
def test_boundary_selection(text, chunk_size, expected_end):
    assert iter_spans(text, chunk_size=chunk_size, overlap=0)[0] == (0, expected_end)


def test_overlap_and_final_chunk():
    assert iter_spans("abcdefghij", chunk_size=4, overlap=2) == [
        (0, 4), (2, 6), (4, 8), (6, 10)
    ]


def test_large_overlap_still_advances_after_boundary_cut():
    assert iter_spans("abc。defghij", chunk_size=8, overlap=7) == [
        (0, 4), (1, 9), (2, 10), (3, 11)
    ]


def test_offsets_preserve_original_text():
    text = "Ａ\r\n\u200b。Ｂxyz"
    spans = iter_spans(text, chunk_size=6, overlap=0)
    assert spans == [(0, 3), (3, 9)]
    assert "".join(text[start:end] for start, end in spans) == text


def test_span_invariants_for_small_inputs():
    for length in range(6):
        for chars in product("a\n。", repeat=length):
            text = "".join(chars)
            for chunk_size in range(1, 7):
                for overlap in range(chunk_size):
                    spans = iter_spans(text, chunk_size=chunk_size, overlap=overlap)
                    if not text:
                        assert spans == []
                        continue
                    assert spans[0][0] == 0
                    assert spans[-1][1] == len(text)
                    covered = set()
                    for start, end in spans:
                        assert 0 <= start < end <= len(text)
                        assert 0 < end - start <= chunk_size
                        covered.update(range(start, end))
                    assert covered == set(range(len(text)))
                    for (start, end), (next_start, _) in zip(spans, spans[1:]):
                        assert end < len(text)
                        assert next_start == max(end - overlap, start + 1)
                        assert start < next_start <= end
