"""建库流水线的契约测试：五文件产物、id 一致性、坏文件隔离、空目录、可直接检索、可复现。"""

import pytest

from ragkit.config import AppConfig
from ragkit.index import build, read_chunks
from ragkit.index.assets import BuiltIndex
from ragkit.retrieval.pipeline import search

QUERY = "容器冷启动"


def _corpus(root):
    """2 个好文档 + 1 个二进制坏文件，返回 (root, 好文档数)。"""
    (root / "a.txt").write_text(
        "容器冷启动 优化指南\n\n冷启动是指容器首次启动时明显变慢的现象。", encoding="utf-8"
    )
    (root / "b.txt").write_text("数据库连接池 的配置方法与参数说明。", encoding="utf-8")
    (root / "bad.md").write_bytes(b"\xff\xfe\x00\x01")
    return root, 2


def _cfg(tmp_path):
    return AppConfig(index_dir=tmp_path / "idx")


def test_build_returns_built_index(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    _, good_docs = _corpus(root)

    built = build(root, _cfg(tmp_path))

    assert isinstance(built, BuiltIndex)
    assert built.dim == _cfg(tmp_path).embedding.dim
    # 每个好文档短于 chunk_size → 各 1 块
    assert len(built.store) == good_docs
    assert len(built.id_to_chunk) == good_docs


def test_build_writes_five_files(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    _corpus(root)
    cfg = _cfg(tmp_path)

    build(root, cfg)

    names = {p.name for p in cfg.index_dir.iterdir()}
    assert names == {
        "manifest.json", "ids.json", "vectors.npy", "metadata.json", "chunks.jsonl",
    }


def test_build_isolates_bad_files(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    _, good_docs = _corpus(root)

    built = build(root, _cfg(tmp_path))

    # 坏文件进 failures，好文件照常进索引
    assert len(built.failures) == 1
    assert built.failures[0].path == "bad.md"
    assert len(built.store) == good_docs


def test_build_empty_dir_produces_empty_index(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()

    built = build(root, _cfg(tmp_path))

    assert len(built.store) == 0
    assert built.store.matrix.shape == (0, built.dim)
    assert read_chunks(_cfg(tmp_path).index_dir / "chunks.jsonl") == []
    assert built.failures == []


def test_build_id_consistency(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    _corpus(root)
    cfg = _cfg(tmp_path)

    built = build(root, cfg)
    disk_ids = {c.chunk_id for c in read_chunks(cfg.index_dir / "chunks.jsonl")}

    assert set(built.store.ids) == disk_ids == set(built.id_to_chunk)


def test_build_supports_search(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    _corpus(root)
    cfg = _cfg(tmp_path)

    built = build(root, cfg)
    result = search(
        QUERY,
        bm25=built.bm25,
        store=built.store,
        id_to_chunk=built.id_to_chunk,
        dim=built.dim,
        retrieval=cfg.retrieval,
    )

    assert all(r.stage == "rerank" for r in result.results)
    # 与 query 词面重叠多的 a.txt 应排第一（hashing 余弦 = token 重叠）
    assert result.results[0].chunk.doc_id == "a.txt"
    assert result.trace.stages  # build 出的资源可完整走一遍流水线


def test_build_reproducible(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    _corpus(root)

    first = build(root, AppConfig(index_dir=tmp_path / "one"))
    second = build(root, AppConfig(index_dir=tmp_path / "two"))

    assert first.store.ids == second.store.ids
    j1 = (tmp_path / "one" / "chunks.jsonl").read_bytes()
    j2 = (tmp_path / "two" / "chunks.jsonl").read_bytes()
    assert j1 == j2
