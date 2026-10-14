"""向量库的契约测试：三元组同序、原子落盘、加载校验、可复现性。"""

import json

import numpy as np
import pytest

from ragkit.errors import StoreCorruptError
from ragkit.stores import VectorStore, load, write

DIM = 4


def test_roundtrip_preserves_ids_vectors_metadata(tmp_path):
    ids = ["c1", "c2", "c3"]
    vectors = [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0]]
    metadata = [
        {"strategy": "fixed", "char_start": 0},
        {"strategy": "fixed", "char_start": 10},
        {"strategy": "fixed", "char_start": 20},
    ]
    write(tmp_path, dim=DIM, ids=ids, vectors=vectors, metadata=metadata)

    store = load(tmp_path)

    assert isinstance(store, VectorStore)
    assert store.ids == ids
    assert store.metadata == metadata
    assert np.allclose(store.matrix, np.array(vectors, dtype=np.float32))


def test_shape_dtype_and_len(tmp_path):
    write(tmp_path, dim=DIM, ids=["a"], vectors=[[1.0, 0, 0, 0]], metadata=[{}])
    store = load(tmp_path)

    assert store.matrix.shape == (1, DIM)
    assert store.matrix.dtype == np.float32
    assert store.dim == DIM
    assert len(store) == 1


@pytest.mark.parametrize("vectors", [[[1.0, 0, 0]], [[1.0, 0, 0, 0, 9.0]]])
def test_vector_length_mismatch_raises(tmp_path, vectors):
    with pytest.raises(ValueError):
        write(tmp_path, dim=DIM, ids=["a"], vectors=vectors, metadata=[{}])


def test_list_length_mismatch_raises(tmp_path):
    with pytest.raises(ValueError):
        write(
            tmp_path,
            dim=DIM,
            ids=["a", "b"],
            vectors=[[1.0, 0, 0, 0]],
            metadata=[{}],
        )


def test_duplicate_ids_raise(tmp_path):
    with pytest.raises(ValueError):
        write(
            tmp_path,
            dim=DIM,
            ids=["a", "a"],
            vectors=[[1.0, 0, 0, 0], [0, 1.0, 0, 0]],
            metadata=[{}, {}],
        )


def test_non_positive_dim_raises(tmp_path):
    with pytest.raises(ValueError):
        write(tmp_path, dim=0, ids=[], vectors=[], metadata=[])


def test_empty_store_roundtrip(tmp_path):
    write(tmp_path, dim=DIM, ids=[], vectors=[], metadata=[])
    store = load(tmp_path)
    assert len(store) == 0
    assert store.matrix.shape == (0, DIM)
    assert store.ids == []
    assert store.metadata == []


def test_load_missing_directory_raises(tmp_path):
    with pytest.raises(StoreCorruptError):
        load(tmp_path / "nope")


def test_corrupt_metadata_raises(tmp_path):
    write(tmp_path, dim=DIM, ids=["a"], vectors=[[1.0, 0, 0, 0]], metadata=[{"x": 1}])
    (tmp_path / "metadata.json").write_text("not json", encoding="utf-8")
    with pytest.raises(StoreCorruptError):
        load(tmp_path)


def test_manifest_dim_mismatch_raises(tmp_path):
    write(tmp_path, dim=DIM, ids=["a"], vectors=[[1.0, 0, 0, 0]], metadata=[{}])
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dim"] = DIM + 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(StoreCorruptError):
        load(tmp_path)


def test_no_tmp_files_left_behind(tmp_path):
    write(tmp_path, dim=DIM, ids=["a"], vectors=[[1.0, 0, 0, 0]], metadata=[{}])
    leftovers = [p.name for p in tmp_path.iterdir() if ".tmp" in p.name]
    assert leftovers == []


def test_metadata_roundtrip_with_chinese(tmp_path):
    metadata = [{"title": "冷启动", "tags": ["性能", "容器"]}]
    write(tmp_path, dim=DIM, ids=["a"], vectors=[[1.0, 0, 0, 0]], metadata=metadata)
    assert load(tmp_path).metadata == metadata


def test_write_is_reproducible(tmp_path):
    ids = ["a", "b"]
    vectors = [[1.0, 0, 0, 0], [0, 1.0, 0, 0]]
    metadata = [{"k": "v"}, {"k": "w"}]

    dir1 = tmp_path / "one"
    dir2 = tmp_path / "two"
    write(dir1, dim=DIM, ids=ids, vectors=vectors, metadata=metadata)
    write(dir2, dim=DIM, ids=ids, vectors=vectors, metadata=metadata)

    for name in ("manifest.json", "ids.json", "metadata.json", "vectors.npy"):
        assert (dir1 / name).read_bytes() == (dir2 / name).read_bytes()
