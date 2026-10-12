import pytest

from ragkit.errors import LoadError
from ragkit.loaders import load_dir, load_file


def test_load_file_returns_document_with_expected_fields(tmp_path):
    file_path = tmp_path / "a.txt"
    file_path.write_text("a", encoding="utf-8")
    doc = load_file(file_path)
    assert doc.doc_id == "a.txt"
    assert doc.source == "a.txt"
    assert doc.text == "a"


def test_load_file_metadata_key_set(tmp_path):
    file_path = tmp_path / "a.txt"
    file_path.write_text("a", encoding="utf-8")
    doc = load_file(file_path)
    assert set(doc.metadata) == {"path", "size", "ext", "encoding", "content_hash"}


def test_load_file_missing_path_raises_load_error(tmp_path):
    with pytest.raises(LoadError):
        load_file(tmp_path / "non_existent.txt")


def test_load_dir_loads_all_supported_files(tmp_path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "c.md").write_text("c", encoding="utf-8")
    (tmp_path / "d.png").write_text("d", encoding="utf-8")
    report = load_dir(tmp_path)
    assert len(report.documents) == 3
    assert report.failures == []


def test_load_dir_skips_dot_prefixed_paths(tmp_path):
    (tmp_path / ".hidden.md").write_text("hidden", encoding="utf-8")
    (tmp_path / ".trash").mkdir()
    (tmp_path / ".trash/x.md").write_text("visible", encoding="utf-8")
    report = load_dir(tmp_path)
    assert len(report.documents) == 0
    assert report.failures == []


def test_load_dir_continues_after_bad_file(tmp_path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_bytes(b"\xff\xfe\x00\x01")
    (tmp_path / "c.md").write_text("c", encoding="utf-8")
    report = load_dir(tmp_path)
    assert len(report.documents) == 2
    assert len(report.failures) == 1
    # path 与 Document.source 同坐标系：相对 root 的 POSIX 路径，而不是绝对路径。
    assert report.failures[0].path == "b.txt"
    assert report.failures[0].error_type == "UnicodeDecodeError"


def test_load_dir_missing_root_raises_file_not_found_error(tmp_path):
    missing_path = tmp_path / "non_existent_dir"
    with pytest.raises(FileNotFoundError):
        load_dir(missing_path)


def test_load_dir_is_sorted(tmp_path):
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "c.md").write_text("c", encoding="utf-8")
    report = load_dir(tmp_path)
    assert [d.source for d in report.documents] == ["a.md", "b.md", "c.md"]


def test_gbk_encoded_file_is_decoded_and_encoding_recorded(tmp_path):
    file_path = tmp_path / "a.txt"
    file_path.write_bytes("冷启动优化".encode("gbk"))
    doc = load_file(file_path)
    assert doc.text == "冷启动优化"
    assert doc.metadata["encoding"] == "gbk"


def test_utf8_bom_is_stripped_and_encoding_recorded(tmp_path):
    file_path = tmp_path / "a.txt"
    file_path.write_bytes("\ufeff标题".encode("utf-8"))
    doc = load_file(file_path)
    assert doc.text.startswith("\ufeff") is False
    # encoding 记录编码家族（utf-8 / gbk），不是 codec 名 utf-8-sig；理由见 load_file docstring。
    assert doc.metadata["encoding"] == "utf-8"


def test_markdown_title_from_first_heading(tmp_path):
    file_path = tmp_path / "a.md"
    file_path.write_text("# 冷启动\n\n正文", encoding="utf-8")
    doc = load_file(file_path)
    assert doc.title == "冷启动"
    assert doc.title in doc.text


def test_markdown_title_falls_back_to_filename(tmp_path):
    file_path = tmp_path / "a.md"
    file_path.write_text("正文没有标题", encoding="utf-8")
    doc = load_file(file_path)
    assert doc.title == "a"


def test_content_hash_changes_when_content_changes(tmp_path):
    file_path = tmp_path / "a.txt"
    file_path.write_text("initial content", encoding="utf-8")
    doc1 = load_file(file_path)
    hash1 = doc1.metadata["content_hash"]

    file_path.write_text("modified content", encoding="utf-8")
    doc2 = load_file(file_path)
    hash2 = doc2.metadata["content_hash"]

    file_path = tmp_path / "a.txt"
    file_path.write_text("initial content", encoding="utf-8")
    doc3 = load_file(file_path)
    hash3 = doc3.metadata["content_hash"]

    assert hash1 != hash2
    assert hash1 == hash3


def test_load_dir_source_is_relative_posix(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub/a.md").write_text("a", encoding="utf-8")
    report = load_dir(tmp_path)
    assert report.documents[0].source == "sub/a.md"
    # 元数据里的 path 也必须同坐标系：绝对路径会泄漏机器信息、并让报告无法跨机器比对。
    assert report.documents[0].metadata["path"] == "sub/a.md"


def test_load_dir_does_not_depend_on_cwd(tmp_path, monkeypatch):
    root = (tmp_path / "docs").resolve()
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")
    (root / "b.md").write_text("b", encoding="utf-8")

    before = load_dir(root)

    monkeypatch.chdir(tmp_path)
    after = load_dir(root)

    assert len(before.documents) == 2
    assert after.documents == before.documents
    assert after.failures == before.failures == []
