import json

import pytest

from ragkit.schemas import (
    Answer,
    Citation,
    Chunk,
    Document,
    RetrievalTrace,
    ScoredChunk,
    StageTrace,
)


def test_document_roundtrip():
    # 构造包含标题和嵌套元数据的文档，检查转为字典后能否还原。
    doc = Document("doc-1", "source", "text", "title", {"tags": ["a", "b"]})
    data = doc.to_dict()
    # 显式锁定 Document 对外序列化的完整键集合，字段顺序可以调整。
    assert set(data) == {"doc_id", "metadata", "source", "text", "title"}
    restored = Document.from_dict(data)
    # dataclass 的相等比较会逐个比较字段值。
    assert restored == doc
    # 确认此文档的字典可以编码为 JSON；若编码失败，异常会使测试失败。
    # ensure_ascii=False 允许中文等非 ASCII 字符直接保留在输出中。
    assert json.dumps(doc.to_dict(), ensure_ascii=False)


def test_chunk_roundtrip():
    # 构造分块样例，包含所属文档、序号以及可选的标题、来源和元数据。
    chunk = Chunk(
        chunk_id="chunk-1",
        doc_id="doc-1",
        text="text",
        ordinal=0,
        score_hint=0.5,
        title="title",
        source="source",
        metadata={"tags": ["a", "b"]},
    )
    data = chunk.to_dict()
    # 显式锁定 Chunk 对外序列化的完整键集合，防止契约键名被悄悄改动。
    assert set(data) == {
        "chunk_id",
        "doc_id",
        "metadata",
        "ordinal",
        "score_hint",
        "source",
        "text",
        "title",
    }
    # 验证分块经过“对象 → 字典 → 对象”后，各字段值保持一致。
    restored = Chunk.from_dict(data)
    assert restored == chunk
    # 确认分块的字典可以编码为 JSON；若包含不可序列化的值，测试会失败。
    assert json.dumps(data, ensure_ascii=False)


def test_document_metadata_default_is_not_shared():
    # 不传元数据时，每个文档应获得独立的默认字典。
    first = Document("doc-1", "source", "text")
    second = Document("doc-2", "source", "text")

    # 只修改第一个文档，检查第二个文档是否受到影响。
    first.metadata["key"] = "value"

    assert second.metadata == {}


def test_document_from_dict_requires_text():
    # 缺少正文时应抛出 ValueError；pytest.raises 捕获异常供后续检查。
    with pytest.raises(ValueError) as exc:
        Document.from_dict({"doc_id": "doc-1", "source": "source"})

    # 错误信息应指出缺少 text，帮助调用者定位输入问题。
    assert "text" in str(exc.value)


@pytest.mark.parametrize("missing_field", ["doc_id", "source", "text"])
def test_document_from_dict_requires_all_fields(missing_field):
    # 参数化会分别测试三个必填字段；每次从完整数据中删除其中一个。
    data = {"doc_id": "doc-1", "source": "source", "text": "text"}
    del data[missing_field]

    # 每种缺失情况都应抛出 ValueError，并在消息中包含对应字段名。
    with pytest.raises(ValueError) as exc:
        Document.from_dict(data)

    assert missing_field in str(exc.value)


@pytest.mark.parametrize("missing_field", ["chunk_id", "doc_id", "text", "ordinal"])
def test_chunk_from_dict_requires_all_fields(missing_field):
    # 分别删除分块的四个必填字段，验证每一个字段都受到缺失检查。
    data = {"chunk_id": "chunk-1", "doc_id": "doc-1", "text": "text", "ordinal": 0}
    del data[missing_field]

    # 统一使用 ValueError 报告缺失字段，而非泄漏字典索引的 KeyError。
    with pytest.raises(ValueError) as exc:
        Chunk.from_dict(data)

    assert missing_field in str(exc.value)


def test_chunk_from_dict_empty_data_reports_required_fields():
    # 空字典缺少所有必填字段，也应通过统一的校验抛出 ValueError。
    with pytest.raises(ValueError) as exc:
        Chunk.from_dict({})

    # 此处仅检查消息中包含 chunk_id，不代表验证了所有缺失字段的提示。
    assert "chunk_id" in str(exc.value)


def test_chunk_from_dict_without_score_hint_uses_default():
    # 旧数据未提供 score_hint 时，应成功加载并使用默认值 0.0。
    data = {"chunk_id": "chunk-1", "doc_id": "doc-1", "text": "text", "ordinal": 0}
    chunk = Chunk.from_dict(data)

    assert chunk.score_hint == 0.0


def test_chunk_from_dict_ignores_unknown_keys():
    # 输入中的未知字段应被忽略，不应成为分块对象的属性。
    data = {
        "chunk_id": "chunk-1",
        "doc_id": "doc-1",
        "text": "text",
        "ordinal": 0,
        "legacy_field": 1,
    }
    chunk = Chunk.from_dict(data)

    assert hasattr(chunk, "legacy_field") is False


def test_scored_chunk_roundtrip():
    scored=ScoredChunk(
        chunk=Chunk(chunk_id="chunk-1", doc_id="doc-1", text="text", ordinal=0),
        score=0.5,
        stage="test",
        sub_scores={"key": 1.0}
    )
    data = scored.to_dict()
    assert set(data) == {"chunk", "score", "stage", "sub_scores"}
    restored = ScoredChunk.from_dict(data)
    assert restored == scored
    # 确认分块的字典可以编码为 JSON；若包含不可序列化的值，测试会失败。
    assert json.dumps(data, ensure_ascii=False)
    assert isinstance(restored.chunk, Chunk)


def test_sub_scores_default_is_not_shared():
    # 不传 sub_scores 时，每个 ScoredChunk 应获得独立的默认字典。
    first = ScoredChunk(
        chunk=Chunk(chunk_id="chunk-1", doc_id="doc-1", text="text", ordinal=0),
        score=0.5,
        stage="test"
    )
    second = ScoredChunk(
        chunk=Chunk(chunk_id="chunk-2", doc_id="doc-2", text="text", ordinal=1),
        score=0.6,
        stage="test"
    )

    # 只修改第一个 ScoredChunk，检查第二个是否受到影响。
    first.sub_scores["key"] = 1.0

    assert second.sub_scores == {}


@pytest.mark.parametrize("missing_field", ["chunk", "score", "stage"])
def test_scored_chunk_from_dict_requires_fields(missing_field):
    data = {
        "chunk": {
            "chunk_id": "chunk-1",
            "doc_id": "doc-1",
            "text": "text",
            "ordinal": 0,
        },
        "score": 0.5,
        "stage": "test",
    }
    del data[missing_field]

    with pytest.raises(ValueError) as exc:
        ScoredChunk.from_dict(data)

    assert missing_field in str(exc.value)


def test_citation_roundtrip():
    citation = Citation(
        index=0,
        source="source",
        snippet="text",
        title="title",
    )
    data = citation.to_dict()
    assert set(data) == {"index", "source", "snippet", "title"}
    restored = Citation.from_dict(data)
    assert restored == citation
    assert json.dumps(data, ensure_ascii=False)


def test_stage_trace_roundtrip():

    trace = StageTrace(
        name="stage-1",
        latency_ms=123.4,
        candidate_count=10
    )
    data = trace.to_dict()
    assert set(data) == {"name", "latency_ms", "candidate_count"}
    restored = StageTrace.from_dict(data)
    assert restored == trace
    assert json.dumps(data, ensure_ascii=False)


def test_retrieval_trace_roundtrip():

    trace1 = StageTrace(
            name="stage-1",
            latency_ms=1.5,
            candidate_count=10
        )
    trace2 = StageTrace(
            name="stage-2",
            latency_ms=2.25,
            candidate_count=20
        )
    trace3 = StageTrace(
            name="stage-3",
            latency_ms=0.75,
            candidate_count=30
        )
    trace=RetrievalTrace(
        stages=[trace1, trace2, trace3]
    )

    data = trace.to_dict()
    assert set(data) == {"stages"}
    restored = RetrievalTrace.from_dict(data)
    assert len(restored.stages) == 3
    assert isinstance(restored.stages[0], StageTrace)
    assert isinstance(restored.stages[1], StageTrace)
    assert isinstance(restored.stages[2], StageTrace)
    assert restored == trace
    assert restored.total_latency_ms() == 4.5
    assert RetrievalTrace().total_latency_ms() == 0.0
    assert json.dumps(data, ensure_ascii=False)


@pytest.mark.parametrize("data", [{"stages": None}, {}])
def test_retrieval_trace_from_dict_null_or_missing_stages(data):
    # JSON null 或缺失字段统一还原为空列表，写出时也保持列表类型。
    trace = RetrievalTrace.from_dict(data)
    assert trace.stages == []
    assert trace.to_dict() == {"stages": []}


@pytest.mark.parametrize("field_name", ["citations", "contexts"])
@pytest.mark.parametrize("missing", [False, True])
def test_answer_from_dict_null_or_missing_list(field_name, missing):
    data = Answer(question="问题", answer="回答").to_dict()
    if missing:
        del data[field_name]
    else:
        data[field_name] = None

    restored = Answer.from_dict(data)
    assert getattr(restored, field_name) == []
    assert restored.to_dict()[field_name] == []


@pytest.mark.parametrize("trace_data", [None, {}, {"stages": None}])
def test_answer_from_dict_distinguishes_none_and_empty_trace(trace_data):
    data = Answer(question="问题", answer="").to_dict()
    data["trace"] = trace_data
    restored = Answer.from_dict(data)
    # 没有轨迹与存在一个空轨迹具有不同语义。
    if trace_data is None:
        assert restored.trace is None
        assert restored.to_dict()["trace"] is None
    else:
        assert isinstance(restored.trace, RetrievalTrace)
        assert restored.trace.stages == []
        assert restored.to_dict()["trace"] == {"stages": []}


def test_stages_default_is_not_shared():

    # 不传 stages 时，每个 RetrievalTrace 应获得独立的默认列表。
    first = RetrievalTrace()
    second = RetrievalTrace()

    # 只修改第一个 RetrievalTrace，检查第二个是否受到影响。
    first.stages.append(StageTrace(name="stage-1", latency_ms=1.0, candidate_count=10))

    assert second.stages == []


def test_answer_roundtrip():
    answer = Answer(
        question="What is the capital of France?",
        answer="Paris",
        citations=[
            Citation(index=0, source="source1", snippet="snippet1", title="title1"),
            Citation(index=1, source="source2", snippet="snippet2", title="title2"),
        ],
        refused=False,
        confidence=0.95,
        contexts=["context1", "context2"],
        trace=RetrievalTrace(stages=[
            StageTrace(name="stage-1", latency_ms=1.0, candidate_count=10),
            StageTrace(name="stage-2", latency_ms=2.0, candidate_count=20),
        ])
    )
    data = answer.to_dict()
    assert set(data) == {"question", "answer", "citations", "refused", "confidence", "contexts", "trace"}
    restored = Answer.from_dict(data)
    assert restored == answer
    assert json.dumps(data, ensure_ascii=False)


def test_answer_roundtrip_without_trace():
    answer = Answer(
        question="What is the capital of France?",
        answer="Paris",
        citations=[
            Citation(index=0, source="source1", snippet="snippet1", title="title1"),
            Citation(index=1, source="source2", snippet="snippet2", title="title2"),
        ],
        refused=False,
        confidence=0.95,
        contexts=["context1", "context2"],
        trace=None
    )
    data = answer.to_dict()
    assert set(data) == {"question", "answer", "citations", "refused", "confidence", "contexts", "trace"}
    restored = Answer.from_dict(data)
    assert restored.trace is None


def test_answer_from_dict_requires_fields():
    data = {
        "question": "What is the capital of France?",
        "answer": "Paris",
        "citations": [],
        "refused": False,
        "confidence": 0.95,
        "contexts": [],
        "trace": None
    }
    for missing_field in ["question", "answer"]:
        test_data = data.copy()
        del test_data[missing_field]
        with pytest.raises(ValueError) as exc:
            Answer.from_dict(test_data)
        assert missing_field in str(exc.value)


def test_answer_from_dict_without_optional_fields():
    data = {
        "question": "What is the capital of France?",
        "answer": "Paris",
    }
    restored = Answer.from_dict(data)
    assert restored.citations == []
    assert restored.refused is False
    assert restored.confidence == 0.0
    assert restored.contexts == []
    assert restored.trace is None
