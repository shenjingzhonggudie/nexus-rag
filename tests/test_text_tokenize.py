from ragkit.text import tokenize, tokenize_bigrams, tokenize_terms


def test_terms_contain_chinese_words():
    test ="容器冷启动时间"
    terms = tokenize_terms(test)
    assert "容器" in terms
    assert "时间" in terms


def test_bigrams_are_adjacent_pairs():
    test = "容器冷启动"
    bigrams = tokenize_bigrams(test)
    assert "容器" in bigrams
    assert  "器冷" in bigrams
    assert  "冷启" in bigrams
    assert  "启动" in bigrams


def test_bigrams_not_generated_for_ascii():
    test = "BM25 python3.12"
    bigrams = tokenize_bigrams(test)
    assert bigrams == []


def test_whitespace_and_pure_punctuation_filtered():
    test = "   ，。！  "
    terms = tokenize_terms(test)
    assert terms == []


def test_url_version_and_numbers_survive():
    test = "https://api.example.com/v1/items、v2.1.3、python3.12、800"
    terms = tokenize_terms(test)
    assert "https" in terms
    assert "v2.1" in terms
    assert "3" in terms
    assert "python3.12" in terms
    assert "800" in terms


def test_mixed_chinese_english_numbers():
    test = "容器 cold 启动 v1.2.3"
    terms = tokenize_terms(test)
    assert "容器" in terms
    assert "cold" in terms
    assert "启动" in terms
    assert "v1.2" in terms
    assert "3" in terms
    


def test_tokenize_is_union_of_two_channels():
    test = "容器 cold 启动"
    terms = tokenize_terms(test)
    bigrams = tokenize_bigrams(test)
    all_tokens = tokenize(test)
    for term in terms:
        assert term in all_tokens
    for bigram in bigrams:
        assert bigram in all_tokens


def test_tokenize_normalizes_input():
    fullwidth = "ＡＢＣ　１２３"
    halfwidth = "ABC 123"
    assert tokenize_terms(fullwidth) == tokenize_terms(halfwidth)


def test_empty_text_returns_empty_list():
    test = ""
    terms = tokenize_terms(test)
    bigrams = tokenize_bigrams(test)
    all_tokens = tokenize(test)
    assert terms == []
    assert bigrams == []
    assert all_tokens == []