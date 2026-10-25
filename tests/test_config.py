import json
from pathlib import Path

import pytest

from ragkit import config
from ragkit.errors import ConfigError


def test_default_config():
    cfg = config.load_config(environ={})
    assert cfg.retrieval.top_k == 20
    assert cfg.retrieval.final_k == 5
    assert cfg.retrieval.fusion_alpha == 0.7
    assert cfg.retrieval.fusion_method == "weighted_rrf"
    assert cfg.rerank.enabled is True
    assert cfg.rerank.local_files_only is True
    assert cfg.llm.provider == "none"


def test_default_yaml_matches_model_defaults():
    """configs/default.yaml 必须与模型默认值逐字段一致。

    不传--config与传configs/default.yaml应相等，包括新的独立重排配置。
    """
    root = Path(__file__).resolve().parents[1]
    from_yaml = config.load_config(root / "configs" / "default.yaml", environ={})
    defaults = config.AppConfig()

    a = from_yaml.model_dump()
    b = defaults.model_dump()
    diff: dict[str, tuple] = {}
    for section, values in b.items():
        if isinstance(values, dict):
            for key, expected in values.items():
                actual = a.get(section, {}).get(key)
                if actual != expected:
                    diff[f"{section}.{key}"] = (actual, expected)
        elif a.get(section) != values:
            diff[section] = (a.get(section), values)

    assert not diff, f"default.yaml 与模型默认值不一致（实际, 期望）：{diff}"


def test_load_from_missing_path_raises(tmp_path: Path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError) as exc:
        config.load_config(missing, environ={})
    assert "missing.yaml" in str(exc.value)


def test_load_from_yaml_overrides(tmp_path: Path):
    yaml_content = """
    retrieval:
        top_k: 30
    """
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content,encoding="utf-8")
    cfg = config.load_config(yaml_file, environ={})
    assert cfg.retrieval.top_k == 30
    assert cfg.retrieval.final_k == 5  # default value
    assert cfg.chunking.chunk_size == 300


def test_empty_file_uses_defaults(tmp_path: Path):
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("")
    cfg = config.load_config(empty_file, environ={})
    assert cfg.retrieval.top_k == 20
    assert cfg.chunking.chunk_size == 300


def test_non_mapping_top_level_rejected(tmp_path: Path):
    # 顶层列表是合法 YAML，但不符合配置要求的键值映射结构。
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text("- a\n- b", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        config.load_config(yaml_file, environ={})
    message = str(exc.value)
    assert "映射" in message or "dict" in message


@pytest.mark.parametrize(
    "yaml_content, expected_fields",
    [
        pytest.param("retrieval: {top_k: 0}", ("top_k",), id="zero-top-k"),
        pytest.param("retrieval: {top_k: -1}", ("top_k",), id="negative-top-k"),
        pytest.param(
            "retrieval: {top_k: 3, final_k: 5}",
            ("top_k", "final_k"),
            id="final-k-exceeds-top-k",
        ),
        pytest.param(
            "chunking: {chunk_size: -1}",
            ("chunk_size",),
            id="negative-chunk-size",
        ),
        pytest.param(
            "chunking: {chunk_size: 400, overlap: 400}",
            ("overlap", "chunk_size"),
            id="overlap-equals-chunk-size",
        ),
    ],
)
def test_invalid_values_rejected(
    tmp_path: Path, yaml_content: str, expected_fields: tuple[str, ...]
):
    yaml_file = tmp_path / "invalid_values.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        config.load_config(yaml_file, environ={})
    message = str(exc.value)
    assert any(field in message for field in expected_fields)


def test_unknown_key_rejected(tmp_path: Path):
    yaml_file = tmp_path / "unknown_key.yaml"
    yaml_file.write_text("retrieval:\n  fusion_type: weighted", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        config.load_config(yaml_file, environ={})
    message = str(exc.value)
    assert "fusion_type" in message


def test_config_roundtrip(tmp_path: Path):
    appconfig = config.AppConfig()
    data=appconfig.snapshot()
    restored=config.AppConfig.model_validate(data)
    assert restored == appconfig


def test_env_overrides_yaml(tmp_path: Path, monkeypatch):
    yaml_content = """
    retrieval:
        top_k: 30
    """
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    # Set environment variable to override top_k

    monkeypatch.setenv("RAG__RETRIEVAL__TOP_K", "40")
    cfg = config.load_config(yaml_file)        # environ=None → 读真实环境
    assert cfg.retrieval.top_k == 40


def test_env_merges_deeply(tmp_path: Path):
    yaml_content = """
    retrieval:
        top_k: 30
        fusion_alpha: 0.8
    """
    environ = {
        "RAG__RETRIEVAL__FINAL_K": "7"
    }
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    cfg = config.load_config(yaml_file, environ=environ)
    assert cfg.retrieval.top_k == 30  # from YAML
    assert cfg.retrieval.fusion_alpha == 0.8  # from YAML
    assert cfg.retrieval.final_k == 7  # from env


def test_env_type_conversion(tmp_path: Path):
    environ = {
        "RAG__retrieval__top_k": "30",
        "RAG__retrieval__sparse_enabled": "false",
        "RAG__embedding__dim": "256",
    }

    cfg = config.load_config(
        path=None,
        environ=environ,
    )

    assert cfg.retrieval.top_k == 30
    assert isinstance(cfg.retrieval.top_k, int)

    assert cfg.retrieval.sparse_enabled is False
    assert isinstance(cfg.retrieval.sparse_enabled, bool)

    assert cfg.embedding.dim == 256
    assert isinstance(cfg.embedding.dim, int)


def test_env_top_level_field(tmp_path: Path):
    environ = {
        "RAG__DATA_DIR": "mydata"
    }

    cfg = config.load_config(
        path=None,
        environ=environ,
    )

    assert cfg.data_dir == Path("mydata")


def test_env_invalid_value_rejected(tmp_path: Path):
    environ = {
        "RAG__RETRIEVAL__TOP_K": "abc"
    }

    with pytest.raises(ConfigError) as exc:
        config.load_config(
            path=None,
            environ=environ,
        )
    message = str(exc.value)
    assert message
    assert "top_k" in message


def test_env_unknown_field_rejected(tmp_path: Path):
    environ = {
        "RAG__RETRIEVAL__TOPKK": "30"
    }

    with pytest.raises(ConfigError) as exc:
        config.load_config(
            path=None,
            environ=environ,
        )
    message = str(exc.value)
    assert message


def test_env_unrelated_variables_ignored(tmp_path: Path):
    environ = {
        "PATH": "/some/path",
        "OTHER__X": "1",
    }

    cfg = config.load_config(
        path=None,
        environ=environ,
    )

    assert cfg == config.load_config(path=None, environ={})


def test_env_ignores_three_level_keys(tmp_path: Path):
    environ = {
        "RAG__A__B__C": "1"
    }

    cfg = config.load_config(
        path=None,
        environ=environ,
    )

    assert cfg


def test_snapshot_masks_api_key(tmp_path: Path):
    yaml_content = """
    llm:
        api_key: "sk-SUPERSECRET123"
    """
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    appconfig = config.load_config(yaml_file, environ={})
    snapshot = appconfig.snapshot()
    assert "sk-SUPERSECRET123" not in json.dumps(snapshot)


def test_snapshot_is_json_serializable(tmp_path: Path):
    yaml_content = """
    """ 
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    appconfig = config.load_config(yaml_file, environ={})
    snapshot = appconfig.snapshot()
    assert json.dumps(snapshot)


def test_snapshot_keeps_other_fields(tmp_path: Path):
    yaml_content = """
    retrieval:
        top_k: 40
    llm:
       api_key: "sk-SUPERSECRET123"
    """
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    appconfig = config.load_config(yaml_file, environ={})
    snapshot = appconfig.snapshot()
    assert snapshot["retrieval"]["top_k"] == 40
    assert snapshot["chunking"]["chunk_size"] == 300  # default value


@pytest.mark.parametrize("legacy,method", [(True,"weighted_rrf"),(False,"rrf"),("false","rrf")])
def test_legacy_fusion_flag_warns_without_enabling_model(legacy, method):
    with pytest.warns(FutureWarning, match="rerank_enabled.*弃用"):
        app = config.AppConfig.model_validate({
            "retrieval": {"rerank_enabled": legacy},
            "rerank": {"enabled": False},
        })
    assert app.retrieval.fusion_method == method
    assert not app.rerank.enabled
    assert "rerank_enabled" not in app.snapshot()["retrieval"]


def test_legacy_and_new_fusion_conflict_is_rejected():
    with pytest.raises(ValueError, match="冲突"):
        config.RetrievalConfig(rerank_enabled=True, fusion_method="rrf")


@pytest.mark.parametrize("yaml,env,expected", [
    ("retrieval: {rerank_enabled: true}",{"RAG__RETRIEVAL__FUSION_METHOD":"rrf"},"rrf"),
    ("retrieval: {fusion_method: rrf}",{"RAG__RETRIEVAL__RERANK_ENABLED":"true"},"weighted_rrf"),
    ("retrieval: {rerank_enabled: true}",{"RAG__RETRIEVAL__RERANK_ENABLED":"false"},"rrf"),
])
def test_legacy_migration_preserves_env_precedence(tmp_path, yaml, env, expected):
    path = tmp_path / "old.yaml"
    path.write_text(yaml,encoding="utf-8")
    with pytest.warns(FutureWarning, match="rerank_enabled"):
        app = config.load_config(path, environ={**env, "RAG__RERANK__ENABLED": "false"})
    assert app.retrieval.fusion_method == expected
    assert not app.rerank.enabled


def test_explicit_model_rerank_is_independent_of_fusion_and_roundtrips():
    app = config.load_config(environ={
        "RAG__RETRIEVAL__FUSION_METHOD":"rrf",
        "RAG__RERANK__ENABLED":"true",
        "RAG__RERANK__MODEL_NAME":"local/reranker",
        "RAG__RERANK__BATCH_SIZE":"4",
        "RAG__RERANK__LOCAL_FILES_ONLY":"true",
    })
    assert app.retrieval.fusion_method == "rrf"
    assert app.rerank.enabled and app.rerank.batch_size == 4
    assert app.rerank.model_name == "local/reranker"
    assert config.AppConfig.model_validate(app.snapshot()) == app


@pytest.mark.parametrize("rerank", [{"model_name":"  "},{"batch_size":0},{"max_length":0},{"device":" "}])
def test_invalid_model_rerank_configuration_is_rejected(rerank):
    with pytest.raises(ValueError):
        config.AppConfig(rerank=rerank)


def test_bad_legacy_boolean_is_a_config_error():
    with pytest.raises(ConfigError, match="rerank_enabled"):
        config.load_config(environ={"RAG__RETRIEVAL__RERANK_ENABLED":"not-a-boolean"})


def test_repr_does_not_leak_api_key(tmp_path: Path):
    yaml_content = """
    llm:
        api_key: "sk-SUPERSECRET123"
    """
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    appconfig = config.load_config(yaml_file, environ={})
    repr_str = repr(appconfig)
    assert "sk-SUPERSECRET123" not in repr_str
