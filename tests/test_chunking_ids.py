"""chunk_id 的契约：格式、稳定、局部、唯一。

ID 的三个性质由不同的"破坏方式"验证：

- 稳定：同一输入跑两次，ID 必须逐字相同（防随机成分混入）；
- 局部：在文档**开头**插入内容后，后面内容未变的块 ID 必须原样保留
  （防位置信息混进 ID —— 这是增量索引能不能做的分水岭）；
- 唯一：同一文档内的块 ID 不得重复（防向量库里互相覆盖）。
"""

from hashlib import sha256

import pytest

from ragkit.chunking import chunk_document, make_chunk_id
from ragkit.schemas import Document


def _document(text: str, doc_id: str = "doc-1") -> Document:
    return Document(doc_id=doc_id, source="docs/example.md", text=text)


# 三个等长段落，每段 10 字符；配合 chunk_size=20 时恰好一段一块。
PARAGRAPHS = "A" * 10 + "\n\n" + "B" * 10 + "\n\n" + "C" * 10


def test_make_chunk_id_format():
    """ID 的形状是契约：doc_id#内容哈希前8位@重复序号，改动即破坏性变更。"""
    chunk_id = make_chunk_id("docs/a.md", "abc", 1)
    expected_hash = sha256("abc".encode("utf-8")).hexdigest()[:8]
    assert chunk_id == f"docs/a.md#{expected_hash}@1"


@pytest.mark.parametrize("occurrence", [0, -1])
def test_make_chunk_id_rejects_occurrence_below_one(occurrence):
    """序号从 1 开始；0 或负数说明调用方算错了，不能悄悄生成怪 ID。"""
    with pytest.raises(ValueError):
        make_chunk_id("doc-1", "abc", occurrence)


def test_same_document_chunked_twice_yields_identical_ids():
    """稳定性：两次分块同一份文档，ID 列表与整个对象都要逐字相同。"""
    first = chunk_document(_document(PARAGRAPHS), chunk_size=20, overlap=0)
    second = chunk_document(_document(PARAGRAPHS), chunk_size=20, overlap=0)

    assert [chunk.chunk_id for chunk in first] == [
        chunk.chunk_id for chunk in second
    ]
    assert first == second


def test_inserting_a_prefix_paragraph_keeps_later_ids():
    """局部性（本轮核心）：ID 不含位置信息。

    在开头插入一段后，ordinal 全部后移，但 B、C 两段的文本没变，
    它们的 ID 必须原样保留 —— 否则"改一处、重建全库"。
    """
    before = chunk_document(_document(PARAGRAPHS), chunk_size=20, overlap=0)
    after = chunk_document(
        _document("Z" * 10 + "\n\n" + PARAGRAPHS), chunk_size=20, overlap=0
    )

    before_ids = [chunk.chunk_id for chunk in before]
    after_ids = [chunk.chunk_id for chunk in after]

    # after 比 before 多出开头那一段，其余必须是同一批 ID、同一顺序。
    assert len(after_ids) == len(before_ids) + 1
    assert after_ids[1:] == before_ids

    # 同时确认 ordinal 确实变了 —— 证明"ID 稳定"不是因为位置没变。
    assert [chunk.ordinal for chunk in before] == [0, 1, 2]
    assert [chunk.ordinal for chunk in after] == [0, 1, 2, 3]


def test_editing_one_paragraph_changes_only_that_id():
    """内容变化的粒度：只有被改的那一块换 ID，其余不受牵连。"""
    edited = "A" * 10 + "\n\n" + "B" * 9 + "X" + "\n\n" + "C" * 10

    before = chunk_document(_document(PARAGRAPHS), chunk_size=20, overlap=0)
    after = chunk_document(_document(edited), chunk_size=20, overlap=0)

    before_ids = [chunk.chunk_id for chunk in before]
    after_ids = [chunk.chunk_id for chunk in after]

    assert len(before_ids) == len(after_ids) == 3
    assert before_ids[0] == after_ids[0]
    assert before_ids[1] != after_ids[1]
    assert before_ids[2] == after_ids[2]


def test_same_text_in_different_documents_gets_different_ids():
    """doc_id 参与身份：两个文档里内容相同的块不能共享 ID。"""
    chunks_a = chunk_document(
        _document(PARAGRAPHS, doc_id="doc-a"), chunk_size=20, overlap=0
    )
    chunks_b = chunk_document(
        _document(PARAGRAPHS, doc_id="doc-b"), chunk_size=20, overlap=0
    )

    assert [chunk.text for chunk in chunks_a] == [chunk.text for chunk in chunks_b]
    assert [chunk.chunk_id for chunk in chunks_a] != [
        chunk.chunk_id for chunk in chunks_b
    ]


def test_chunk_ids_are_unique_within_a_document():
    """唯一性：块 ID 撞车会让向量库后写覆盖前写，检索结果莫名少内容。"""
    chunks = chunk_document(_document("ab" * 40), chunk_size=7, overlap=2)
    ids = [chunk.chunk_id for chunk in chunks]

    assert len(ids) == len(set(ids))
