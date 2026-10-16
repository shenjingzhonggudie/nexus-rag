"""BM25 的契约测试：公式正确性、词频/罕见词/长度三个直觉、参数化、边界、可复现。"""

import pytest

from ragkit.retrieval.bm25 import BM25Index
from ragkit.schemas import Chunk


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(chunk_id=chunk_id, doc_id="doc", text=text, ordinal=0)


def _patch_tokenize(monkeypatch, token_map):
    """用固定 token 表替换 tokenize，摆脱 jieba 词典版本，让分数可手算。"""
    monkeypatch.setattr(
        "ragkit.retrieval.bm25.tokenize",
        lambda text: list(token_map[text]),
    )


def test_hand_calculated_example(monkeypatch):
    # 语料：D1=["a","b"]  D2=["a","a"]  D3=["c","d"]，N=3，avgdl=2
    _patch_tokenize(monkeypatch, {
        "D1": ["a", "b"], "D2": ["a", "a"], "D3": ["c", "d"],
        "qa": ["a"], "qb": ["b"],
    })
    idx = BM25Index([_chunk("c1", "D1"), _chunk("c2", "D2"), _chunk("c3", "D3")])

    top = idx.search("qa", top_k=10)

    # 词频更高的 D2 排在 D1 前面；D3 不含 "a" 被排除
    assert [r.chunk.chunk_id for r in top] == ["c2", "c1"]
    # 手算值：0.470·(2·2.5)/(2+1.5)≈0.671，0.470·(1·2.5)/(1+1.5)=0.470
    assert top[0].score == pytest.approx(0.671, abs=1e-3)
    assert top[1].score == pytest.approx(0.470, abs=1e-3)


def test_rare_term_scores_higher(monkeypatch):
    _patch_tokenize(monkeypatch, {
        "D1": ["a", "b"], "D2": ["a", "a"], "D3": ["c", "d"],
        "qa": ["a"], "qb": ["b"],
    })
    idx = BM25Index([_chunk("c1", "D1"), _chunk("c2", "D2"), _chunk("c3", "D3")])

    common = {r.chunk.chunk_id: r.score for r in idx.search("qa", top_k=10)}
    rare = {r.chunk.chunk_id: r.score for r in idx.search("qb", top_k=10)}

    # 罕见词 "b"(df=1) 在 c1 的分 > 常见词 "a"(df=2) 在 c1 的分
    assert rare["c1"] > common["c1"]


def test_longer_chunk_is_penalized(monkeypatch):
    _patch_tokenize(monkeypatch, {
        "short": ["a", "b"],
        "long": ["a", "b", "x", "y", "z", "w"],
        "qa": ["a"],
    })
    idx = BM25Index([_chunk("short", "short"), _chunk("long", "long")])
    top = idx.search("qa", top_k=10)
    # 同样 tf=1，短块因长度归一化排在长块前面
    assert [r.chunk.chunk_id for r in top] == ["short", "long"]


def test_k1_zero_makes_tf_irrelevant(monkeypatch):
    _patch_tokenize(monkeypatch, {
        "once": ["a"], "thrice": ["a", "a", "a"], "qa": ["a"],
    })
    idx = BM25Index(
        [_chunk("once", "once"), _chunk("thrice", "thrice")], k1=0.0
    )
    scores = {r.chunk.chunk_id: r.score for r in idx.search("qa", top_k=10)}
    # k1=0 时 tf 项退化为 1，词频不再影响分数
    assert scores["once"] == pytest.approx(scores["thrice"])


def test_empty_query_returns_zero_score_chunks(monkeypatch):
    # 空 query 与 dense 对齐：返回 top_k 个分数全 0 的块，而非空列表
    _patch_tokenize(monkeypatch, {"D1": ["a"], "": []})
    idx = BM25Index([_chunk("c1", "D1")])
    result = idx.search("", top_k=10)
    assert [r.chunk.chunk_id for r in result] == ["c1"]
    assert all(r.score == 0.0 for r in result)
    assert all(r.stage == "bm25" for r in result)


def test_empty_corpus_returns_empty(monkeypatch):
    _patch_tokenize(monkeypatch, {"qa": ["a"]})
    idx = BM25Index([])
    assert idx.search("qa", top_k=10) == []


def test_unknown_query_terms_return_empty(monkeypatch):
    _patch_tokenize(monkeypatch, {"D1": ["c", "d"], "qz": ["z"]})
    idx = BM25Index([_chunk("c1", "D1")])
    # "z" 不在语料里 → df=0 → 不参与 → 空结果
    assert idx.search("qz", top_k=10) == []


def test_stage_and_top_k(monkeypatch):
    _patch_tokenize(monkeypatch, {
        "d1": ["a"], "d2": ["a", "a"], "d3": ["a", "a", "a"], "qa": ["a"],
    })
    idx = BM25Index([_chunk("c1", "d1"), _chunk("c2", "d2"), _chunk("c3", "d3")])
    top = idx.search("qa", top_k=2)
    assert [r.chunk.chunk_id for r in top] == ["c3", "c2"]
    assert all(r.stage == "bm25" for r in top)


def test_query_is_normalized():
    # 真实 tokenize：全角 ＡＢＣ 经 NFKC 归一化为 ABC，命中同一块
    idx = BM25Index([_chunk("c1", "ABC")])
    half = idx.search("ABC", top_k=10)
    full = idx.search("ＡＢＣ", top_k=10)
    assert [r.chunk.chunk_id for r in half] == ["c1"]
    assert [r.chunk.chunk_id for r in full] == [r.chunk.chunk_id for r in half]


def test_deterministic(monkeypatch):
    _patch_tokenize(monkeypatch, {"d1": ["a"], "d2": ["a", "a"], "qa": ["a"]})
    idx = BM25Index([_chunk("c1", "d1"), _chunk("c2", "d2")])
    first = [(r.chunk.chunk_id, r.score) for r in idx.search("qa")]
    second = [(r.chunk.chunk_id, r.score) for r in idx.search("qa")]
    assert first == second


def test_top_k_limits_results(monkeypatch):
    _patch_tokenize(monkeypatch, {
        "d1": ["a"], "d2": ["a", "a"], "d3": ["a", "a", "a"], "qa": ["a"],
    })
    idx = BM25Index([_chunk("c1", "d1"), _chunk("c2", "d2"), _chunk("c3", "d3")])
    assert len(idx.search("qa", top_k=1)) == 1
