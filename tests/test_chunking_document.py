from hashlib import sha256

import pytest

from ragkit.chunking.document import chunk_document
from ragkit.schemas import Document
from ragkit.text.normalize import normalize_text


def test_chunk_document_preserves_normalized_offsets_and_source_fields():
    document = Document(
        doc_id="doc-1",
        source="docs/example.md",
        text="ＡＢ\r\n正文。",
        title="示例",
    )

    chunks = chunk_document(document, chunk_size=3, overlap=0)
    normalized = normalize_text(document.text)

    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    assert all(
        chunk.text == normalized[
            chunk.metadata["char_start"]:chunk.metadata["char_end"]
        ]
        for chunk in chunks
    )
    assert all(
        (chunk.doc_id, chunk.source, chunk.title)
        == (document.doc_id, document.source, document.title)
        for chunk in chunks
    )
    assert all(
        set(chunk.metadata)
        == {"strategy", "char_start", "char_end", "content_hash"}
        for chunk in chunks
    )
    assert all(chunk.metadata["strategy"] == "fixed" for chunk in chunks)
    assert all(
        chunk.metadata["content_hash"]
        == sha256(chunk.text.encode("utf-8")).hexdigest()[:16]
        for chunk in chunks
    )


def test_repeated_chunk_ids_count_using_full_text_hash_occurrences():
    # 用汉字而不是 "aaaaaa"：每块 16 个字，有效长度 16 高于 _MIN_CHUNK_LEN=10，
    # 否则会被碎块闸门过滤，测不到"重复内容各自编号"这个契约。
    document = Document(doc_id="doc-1", source="source", text="中文内容测试文本" * 6)

    chunks = chunk_document(document, chunk_size=16, overlap=0)

    assert [chunk.text for chunk in chunks] == ["中文内容测试文本中文内容测试文本"] * 3
    assert [chunk.chunk_id.rsplit("@", 1)[1] for chunk in chunks] == ["1", "2", "3"]


def test_chunk_document_empty_text_returns_no_chunks():
    assert chunk_document(Document(doc_id="doc-1", source="source", text="")) == []


@pytest.mark.parametrize(
    "chunk_size, overlap",
    [(0, 0), (-1, 0), (4, -1), (4, 4), (4, 5)],
)
def test_chunk_document_rejects_invalid_parameters(chunk_size, overlap):
    with pytest.raises(ValueError):
        chunk_document(
            Document(doc_id="doc-1", source="source", text="text"),
            chunk_size=chunk_size,
            overlap=overlap,
        )
