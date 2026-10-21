"""生成层的契约测试：正常组装、拒答、fail-fast、序列化、端到端链路。"""

import json

import pytest

from ragkit.config import AppConfig, LLMConfig
from ragkit.generation import answer_question
from ragkit.index import build
from ragkit.retrieval.pipeline import search
from ragkit.retrieval.result import RetrievalResult
from ragkit.schemas import Chunk, RetrievalTrace, ScoredChunk, StageTrace


def _scored(chunk_id, text, score, *, source="a.txt", title="标题"):
    chunk = Chunk(
        chunk_id=chunk_id, doc_id="d", text=text, ordinal=0, source=source, title=title
    )
    return ScoredChunk(chunk=chunk, score=score, stage="rerank")


def _result(items, match_score=None):
    """items: (chunk_id, text, score) 三元组列表；match_score 是拒答判据。"""
    trace = RetrievalTrace(
        stages=[StageTrace(name="rerank", latency_ms=1.0, candidate_count=len(items))]
    )
    return RetrievalResult(
        results=[_scored(cid, text, score) for cid, text, score in items],
        trace=trace,
        match_score=match_score,
    )


def test_normal_answer_assembly():
    result = _result([("a#1@0", "第一块原文", 0.9), ("b#2@0", "第二块原文", 0.5)])

    answer = answer_question("问题？", result, llm=LLMConfig())

    assert answer.question == "问题？"
    assert answer.refused is False
    assert answer.answer == "第一块原文"          # 抽取式：top1 原文
    assert answer.contexts == ["第一块原文", "第二块原文"]
    assert answer.confidence == 0.9               # rerank 分搬运
    assert answer.trace is result.trace            # 原样挂载（同一个对象）


def test_citations_index_and_order():
    result = _result([("a#1@0", "A 原文", 0.9), ("b#2@0", "B 原文", 0.5), ("c#3@0", "C 原文", 0.2)])

    answer = answer_question("问题？", result, llm=LLMConfig())

    assert [c.index for c in answer.citations] == [1, 2, 3]     # 编号从 1 起
    assert [c.snippet for c in answer.citations] == ["A 原文", "B 原文", "C 原文"]
    assert [c.source for c in answer.citations] == ["a.txt"] * 3
    assert all(c.title == "标题" for c in answer.citations)


def test_refused_when_results_empty():
    result = _result([])

    answer = answer_question("问题？", result, llm=LLMConfig())

    assert answer.refused is True
    assert answer.answer == ""
    assert answer.citations == []
    assert answer.contexts == []
    assert answer.confidence == 0.0
    assert answer.trace is result.trace             # 拒答也挂：检索确实发生了


def test_refused_when_match_score_below_threshold():
    # 有结果但实词覆盖率低 → 按阈值拒答。稠密腿永远返回 top_k，所以
    # "结果不为空"不能证明"语料里有答案"，这正是阈值判据要补的洞。
    result = _result([("a#1@0", "不相关原文", 0.02)], match_score=0.3)

    answer = answer_question(
        "Redis 的持久化有哪几种方式？", result, llm=LLMConfig(), refuse_threshold=0.5
    )

    assert answer.refused is True
    assert answer.answer == ""
    assert answer.citations == []
    assert answer.trace is result.trace


def test_not_refused_when_match_score_above_threshold():
    result = _result([("a#1@0", "相关原文", 0.02)], match_score=0.8)

    answer = answer_question("问题？", result, llm=LLMConfig(), refuse_threshold=0.5)

    assert answer.refused is False
    assert answer.answer == "相关原文"


def test_threshold_zero_disables_score_check():
    # 阈值 0 = 不启用分数判据，只有"结果为空"才拒答（向后兼容的默认）
    result = _result([("a#1@0", "原文", 0.02)], match_score=0.0)

    answer = answer_question("问题？", result, llm=LLMConfig(), refuse_threshold=0.0)

    assert answer.refused is False


def test_none_match_score_does_not_refuse():
    # match_score=None（稀疏腿关闭、或查询无实词）表示"无判定信号"，不该拒答
    result = _result([("a#1@0", "原文", 0.02)], match_score=None)

    answer = answer_question("问题？", result, llm=LLMConfig(), refuse_threshold=0.5)

    assert answer.refused is False


def test_openai_compatible_raises_not_implemented():
    result = _result([("a#1@0", "原文", 0.9)])

    with pytest.raises(NotImplementedError):
        answer_question("问题？", result, llm=LLMConfig(provider="openai_compatible"))


def test_answer_is_json_serializable():
    result = _result([("a#1@0", "第一块原文", 0.9), ("b#2@0", "第二块原文", 0.5)])

    answer = answer_question("问题？", result, llm=LLMConfig())

    # 生成层是第一个把 Citation / trace 真正塞进 Answer 的地方，嵌套必须全基础类型
    data = json.loads(json.dumps(answer.to_dict(), ensure_ascii=False))
    assert data["citations"][0] == {
        "index": 1, "source": "a.txt", "snippet": "第一块原文", "title": "标题",
    }
    assert data["trace"]["stages"][0]["name"] == "rerank"


def _search_on(built, cfg, query):
    return search(
        query,
        bm25=built.bm25,
        store=built.store,
        id_to_chunk=built.id_to_chunk,
        dim=built.dim,
        retrieval=cfg.retrieval,
    )


def test_end_to_end_build_search_answer(tmp_path):
    # 正常链路：build → search → answer_question
    root = tmp_path / "raw"
    root.mkdir()
    (root / "a.txt").write_text(
        "容器冷启动 优化指南\n\n冷启动是指容器首次启动时明显变慢的现象。", encoding="utf-8"
    )
    (root / "b.txt").write_text("数据库连接池 的配置方法与参数说明。", encoding="utf-8")
    cfg = AppConfig(index_dir=tmp_path / "idx")

    built = build(root, cfg)
    result = _search_on(built, cfg, "容器冷启动")
    answer = answer_question("容器冷启动怎么优化？", result, llm=cfg.llm)

    assert not answer.refused
    assert answer.answer == result.results[0].chunk.text
    assert answer.citations[0].source == "a.txt"     # 相关文档可溯源
    json.dumps(answer.to_dict(), ensure_ascii=False)  # 端到端也要可序列化

    # 拒答链路：空语料 → 空 results → 拒答
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    cfg2 = AppConfig(index_dir=tmp_path / "idx2")
    built2 = build(empty_root, cfg2)
    result2 = _search_on(built2, cfg2, "任何问题")
    answer2 = answer_question("任何问题", result2, llm=cfg2.llm)

    assert answer2.refused
    assert answer2.answer == ""
    assert answer2.citations == []
