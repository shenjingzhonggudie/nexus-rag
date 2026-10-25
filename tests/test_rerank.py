"""CrossEncoder 契约测试：只使用 fake 依赖，不导入真实 torch/ST 或下载权重。"""

import builtins
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, Event, Lock
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from ragkit.errors import RerankError
from ragkit.retrieval.rerank import rerank
from ragkit.schemas import Chunk, ScoredChunk


rerank_module = importlib.import_module("ragkit.retrieval.rerank")


@pytest.fixture(autouse=True)
def fake_libraries(monkeypatch):
    """所有加载路径都注入 fake；不同测试之间清空模块自己的缓存。"""
    runtime = SimpleNamespace(
        constructions=[],
        predictions=[],
        num_labels=1,
        load_error=None,
        load_hook=None,
        predict_error=None,
        score_fn=lambda pairs: np.arange(len(pairs), dtype=float),
    )

    class Identity:
        pass

    class FakeCrossEncoder:
        def __init__(self, model_name, **kwargs):
            runtime.constructions.append((model_name, kwargs))
            if runtime.load_error is not None:
                raise runtime.load_error
            if runtime.load_hook is not None:
                runtime.load_hook()
            self.num_labels = runtime.num_labels

        def predict(self, pairs, **kwargs):
            runtime.predictions.append((list(pairs), kwargs))
            if runtime.predict_error is not None:
                raise runtime.predict_error
            return runtime.score_fn(pairs)

    torch = ModuleType("torch")
    torch.nn = SimpleNamespace(Identity=Identity)
    sentence_transformers = ModuleType("sentence_transformers")
    sentence_transformers.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)
    runtime.identity_type = Identity
    rerank_module._MODEL_CACHE.clear()
    yield runtime
    rerank_module._MODEL_CACHE.clear()


def _candidate(chunk_id, *, text=None, score=100.0):
    return ScoredChunk(
        chunk=Chunk(
            chunk_id=chunk_id,
            doc_id="doc",
            text=text if text is not None else chunk_id,
            ordinal=0,
            title="标题不能代替正文",
            metadata={"nested": {"value": "kept"}},
        ),
        score=score,
        stage="fusion",
        sub_scores={"bm25": 0.9},
    )


def _ids(results):
    return [result.chunk.chunk_id for result in results]


def test_query_document_pairs_can_reverse_fusion_order(fake_libraries):
    candidates = [
        _candidate("cat", text="猫的饲养", score=9999.0),
        _candidate("dog", text="狗的饲养", score=-9999.0),
    ]
    fake_libraries.score_fn = lambda pairs: np.array(
        [8.0 if query in body else -3.0 for query, body in pairs]
    )

    dogs = rerank("狗", candidates, final_k=2)
    cats = rerank("猫", candidates, final_k=2)

    assert _ids(dogs) == ["dog", "cat"]
    assert _ids(cats) == ["cat", "dog"]
    assert [result.score for result in dogs] == [8.0, -3.0]
    assert all(result.stage == "rerank" for result in dogs)
    assert fake_libraries.predictions[0][0] == [("狗", "猫的饲养"), ("狗", "狗的饲养")]


def test_batches_all_unique_candidates_before_final_k(fake_libraries):
    candidates = [_candidate(str(i)) for i in range(5)]

    out = rerank("query", candidates, final_k=1, batch_size=2)

    assert _ids(out) == ["4"]
    pairs, kwargs = fake_libraries.predictions[0]
    assert len(pairs) == 5
    assert kwargs == {
        "batch_size": 2,
        "show_progress_bar": False,
        "convert_to_numpy": True,
    }


def test_tied_logits_keep_fusion_order_with_negative_scores(fake_libraries):
    fake_libraries.score_fn = lambda pairs: np.array([-2.0, -2.0, -10.0])
    out = rerank("q", [_candidate("b"), _candidate("a"), _candidate("c")], final_k=5)
    assert _ids(out) == ["b", "a", "c"]
    assert [result.score for result in out] == [-2.0, -2.0, -10.0]


def test_no_mutation_of_candidates_chunks_metadata_or_sub_scores(fake_libraries):
    candidates = [_candidate("a"), _candidate("b")]
    snapshot = deepcopy(candidates)

    out = rerank(" q ", candidates, final_k=2)

    assert candidates == snapshot
    assert out[0] is not candidates[1]
    assert out[0].chunk is candidates[1].chunk
    assert out[0].sub_scores == candidates[1].sub_scores
    assert out[0].sub_scores is not candidates[1].sub_scores
    assert fake_libraries.predictions[0][0] == [(" q ", "a"), (" q ", "b")]


def test_duplicate_id_keeps_first_body_and_scores_each_id_once(fake_libraries):
    first = _candidate("a", text="first")
    duplicate = _candidate("a", text="duplicate", score=1e9)
    second = _candidate("b", text="second")

    out = rerank("q", [first, second, duplicate], final_k=10)

    assert _ids(out) == ["b", "a"]
    assert out[1].chunk is first.chunk
    assert fake_libraries.predictions[0][0] == [("q", "first"), ("q", "second")]


def test_empty_candidates_do_not_load_even_with_empty_query(fake_libraries, monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    assert rerank(" ", [], final_k=5) == []
    assert fake_libraries.constructions == []


def test_import_is_lazy_for_optional_dependencies(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "sentence_transformers"}:
            raise AssertionError(f"unexpected eager import: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    importlib.reload(rerank_module)


@pytest.mark.parametrize("query", ["", " \t\n", None, 12])
def test_nonempty_candidates_require_nonblank_query(query, fake_libraries):
    with pytest.raises(ValueError, match="query"):
        rerank(query, [_candidate("a")], final_k=1)
    assert fake_libraries.constructions == []


@pytest.mark.parametrize("name", ["final_k", "batch_size", "max_length"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5, "2", None])
def test_invalid_integer_parameters_fail_before_model_load(name, value, fake_libraries):
    kwargs = {"final_k": 1, name: value}
    with pytest.raises(ValueError, match=name):
        rerank("q", [], **kwargs)
    assert fake_libraries.constructions == []


@pytest.mark.parametrize("model_name", ["", " \t", None, 1])
def test_invalid_model_name_fails_directly(model_name, fake_libraries):
    with pytest.raises(ValueError, match="model_name"):
        rerank("q", [_candidate("a")], model_name=model_name, final_k=1)
    assert fake_libraries.constructions == []


def test_constructor_preserves_native_head_and_requests_raw_logits(fake_libraries):
    rerank("q", [_candidate("a")], final_k=1)
    name, kwargs = fake_libraries.constructions[0]
    assert name == "BAAI/bge-reranker-base"
    assert kwargs == {
        "max_length": 512,
        "device": "cpu",
        "local_files_only": True,
        "trust_remote_code": False,
        "activation_fn": kwargs["activation_fn"],
    }
    assert isinstance(kwargs["activation_fn"], fake_libraries.identity_type)
    assert "num_labels" not in kwargs


@pytest.mark.parametrize("num_labels", [0, 2, 3, None, True, 1.0])
def test_non_single_label_models_fail_before_inference(num_labels, fake_libraries):
    fake_libraries.num_labels = num_labels
    with pytest.raises(RerankError, match="natively have num_labels=1"):
        rerank("q", [_candidate("a")], final_k=1)
    assert fake_libraries.predictions == []
    assert not rerank_module._MODEL_CACHE


@pytest.mark.parametrize("dependency", ["torch", "sentence_transformers"])
def test_missing_dependency_raises_domain_error(dependency, monkeypatch):
    monkeypatch.setitem(sys.modules, dependency, None)
    with pytest.raises(RerankError, match="requires sentence-transformers") as error:
        rerank("q", [_candidate("a")], final_k=1)
    assert isinstance(error.value.__cause__, ImportError)


def test_offline_missing_model_raises_clear_error_and_can_retry(fake_libraries):
    fake_libraries.load_error = OSError("not found in local cache")
    with pytest.raises(RerankError, match="local_files_only=True.*local cache") as error:
        rerank("q", [_candidate("a")], final_k=1)
    assert isinstance(error.value.__cause__, OSError)
    assert not rerank_module._MODEL_CACHE
    fake_libraries.load_error = None
    assert _ids(rerank("q", [_candidate("a")], final_k=1)) == ["a"]
    assert len(fake_libraries.constructions) == 2


def test_inference_failure_never_returns_fusion_results(fake_libraries):
    fake_libraries.predict_error = RuntimeError("bad batch")
    candidates = [_candidate("a"), _candidate("b")]
    snapshot = deepcopy(candidates)
    with pytest.raises(RerankError, match="inference failed: bad batch") as error:
        rerank("q", candidates, final_k=1)
    assert isinstance(error.value.__cause__, RuntimeError)
    assert candidates == snapshot


@pytest.mark.parametrize(
    "scores",
    [np.array([0.0, 4.0]), np.array([[0.0], [4.0]]), np.array([0, 4])],
)
def test_only_vector_or_single_column_scores_are_accepted(scores, fake_libraries):
    fake_libraries.score_fn = lambda pairs: scores
    out = rerank("q", [_candidate("a"), _candidate("b")], final_k=2)
    assert _ids(out) == ["b", "a"]
    assert [result.score for result in out] == [4.0, 0.0]


@pytest.mark.parametrize(
    "scores",
    [
        np.array(1.0),
        np.array([]),
        np.array([1.0]),
        np.array([1.0, 2.0, 3.0]),
        np.array([[1.0, 2.0]]),
        np.array([[1.0, 2.0], [3.0, 4.0]]),
        np.ones((2, 1, 1)),
    ],
)
def test_wrong_score_count_or_shape_raises(scores, fake_libraries):
    fake_libraries.score_fn = lambda pairs: scores
    with pytest.raises(RerankError, match="score shape"):
        rerank("q", [_candidate("a"), _candidate("b")], final_k=2)


@pytest.mark.parametrize(
    "scores",
    [
        np.array(["1", "2"]),
        np.array([True, False]),
        np.array([1.0, object()], dtype=object),
        np.array([1j, 2j]),
    ],
)
def test_non_real_scores_raise(scores, fake_libraries):
    fake_libraries.score_fn = lambda pairs: scores
    with pytest.raises(RerankError, match="real numbers"):
        rerank("q", [_candidate("a"), _candidate("b")], final_k=2)


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_scores_raise(value, fake_libraries):
    fake_libraries.score_fn = lambda pairs: np.array([1.0, value])
    with pytest.raises(RerankError, match="finite"):
        rerank("q", [_candidate("a"), _candidate("b")], final_k=2)


def test_one_candidate_still_requires_a_score_vector(fake_libraries):
    fake_libraries.score_fn = lambda pairs: np.array(-3.0)
    with pytest.raises(RerankError, match="score shape"):
        rerank("q", [_candidate("a")], final_k=1)
    fake_libraries.score_fn = lambda pairs: np.array([[-3.0]])
    assert rerank("q", [_candidate("a")], final_k=1)[0].score == -3.0


def test_raw_numeric_precision_is_preserved_when_sorting(fake_libraries):
    fake_libraries.score_fn = lambda pairs: np.array([2**53, 2**53 + 1], dtype=np.uint64)
    out = rerank("q", [_candidate("a"), _candidate("b")], final_k=2)
    assert _ids(out) == ["b", "a"]


def test_python_float_conversion_must_remain_finite(fake_libraries, monkeypatch):
    # 注入转换溢出，避免测试依赖各平台 longdouble 的具体精度。
    monkeypatch.setattr(rerank_module, "float", lambda value: float("inf"), raising=False)
    with pytest.raises(RerankError, match="remain finite"):
        rerank("q", [_candidate("a")], final_k=1)
    monkeypatch.delattr(rerank_module, "float")


def test_cache_key_includes_model_device_length_and_offline_policy(fake_libraries):
    candidates = [_candidate("a")]
    rerank("q", candidates, final_k=1)
    rerank("another query", candidates, final_k=3, batch_size=1)
    assert len(fake_libraries.constructions) == 1

    for kwargs in (
        {"model_name": "another-model"},
        {"device": "cuda:0"},
        {"max_length": 256},
        {"local_files_only": False},
    ):
        rerank("q", candidates, final_k=1, **kwargs)

    assert len(fake_libraries.constructions) == 5
    rerank("offline again", candidates, final_k=1)
    assert len(fake_libraries.constructions) == 5
    assert fake_libraries.constructions[0][1]["local_files_only"] is True
    assert fake_libraries.constructions[-1][1]["local_files_only"] is False


def test_concurrent_requests_share_one_model(fake_libraries, monkeypatch):
    barrier = Barrier(4)
    all_entered_loader = Event()
    release_constructor = Event()
    count_lock = Lock()
    entries = 0
    original_loader = rerank_module._load_model

    def observed_loader(*args):
        nonlocal entries
        with count_lock:
            entries += 1
            if entries == 4:
                all_entered_loader.set()
        return original_loader(*args)

    def slow_constructor():
        assert release_constructor.wait(timeout=5)

    fake_libraries.load_hook = slow_constructor
    monkeypatch.setattr(rerank_module, "_load_model", observed_loader)

    def request(index):
        barrier.wait(timeout=5)
        return rerank(str(index), [_candidate("a")], final_k=1)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(request, index) for index in range(4)]
        try:
            assert all_entered_loader.wait(timeout=5)
        finally:
            release_constructor.set()
        outputs = [future.result(timeout=5) for future in futures]

    assert all(_ids(output) == ["a"] for output in outputs)
    assert len(fake_libraries.constructions) == 1
    assert len(fake_libraries.predictions) == 4
