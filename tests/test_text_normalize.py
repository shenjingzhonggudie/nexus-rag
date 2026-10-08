from ragkit.text import normalize_text


def test_crlf_and_cr_normalized_to_lf():
    test ="aa\r\naaa\raaaa"
    assert "aa\naaa\naaaa" == normalize_text(test)


def test_nfkc_converts_fullwidth_ascii():
    test="ＡＢＣ１２３，："
    assert "ABC123,:" == normalize_text(test)


def test_nfkc_keeps_chinese_punctuation():
    test="。、；"
    assert "。、;"== normalize_text(test)


def test_zero_width_and_control_chars_removed():
    test ="aa\u200baaa\ufeffaaa\x00aa"
    assert "aaaaaaaaaa"== normalize_text(test)


def test_line_trailing_spaces_and_tabs_stripped():
    test ="aa\taa "
    assert "aa aa"== normalize_text(test)


def test_blank_lines_collapsed():
    test ="aa\n\n\n\n\nbbcc"
    assert "aa\n\nbbcc" == normalize_text(test)


def test_punctuation_and_newlines_preserved():
    test ="aa,.\nbb;:"
    assert "aa,.\nbb;:" == normalize_text(test)


def test_normalize_is_idempotent():
    test ="aa\r\naaa\raaaa"
    normalized_once = normalize_text(test)
    normalized_twice = normalize_text(normalized_once)
    assert normalized_once == normalized_twice


def test_empty_text():
    test =""
    assert "" == normalize_text(test)