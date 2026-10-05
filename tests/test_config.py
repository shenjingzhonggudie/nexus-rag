from pathlib import Path

import pytest

from ragkit import config
from ragkit.errors import ConfigError


def test_default_config():
    cfg = config.load_config()
    assert cfg.retrieval.top_k == 20
    assert cfg.retrieval.final_k == 5
    assert cfg.retrieval.fusion == "rrf"
    assert cfg.llm.provider == "none"


def test_load_from_missing_path_raises(tmp_path: Path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError) as exc:
        config.load_config(missing)
    assert "missing.yaml" in str(exc.value)


def test_load_from_yaml_overrides(tmp_path: Path):
    yaml_content = """
    retrieval:
        top_k: 30
    """
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content,encoding="utf-8")
    cfg = config.load_config(yaml_file)
    assert cfg.retrieval.top_k == 30
    assert cfg.retrieval.final_k == 5  # default value
    assert cfg.chunking.chunk_size == 400


def test_empty_file_uses_defaults(tmp_path: Path):
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("")
    cfg = config.load_config(empty_file)
    assert cfg.retrieval.top_k == 20
    assert cfg.chunking.chunk_size == 400


def test_non_mapping_top_level_rejected(tmp_path: Path):
    # 顶层列表是合法 YAML，但不符合配置要求的键值映射结构。
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text("- a\n- b", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        config.load_config(yaml_file)
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
        pytest.param("retrieval: {fusion: bm25}", ("fusion",), id="invalid-fusion"),
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
        config.load_config(yaml_file)
    message = str(exc.value)
    assert any(field in message for field in expected_fields)


def test_unknown_key_rejected(tmp_path: Path):
    yaml_file = tmp_path / "unknown_key.yaml"
    yaml_file.write_text("retrieval:\n  fusion_type: weighted", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        config.load_config(yaml_file)
    message = str(exc.value)
    assert "fusion_type" in message


def test_config_roundtrip(tmp_path: Path):
    appconfig = config.AppConfig()
    data=appconfig.model_dump()
    restored=config.AppConfig.model_validate(data)
    assert restored == appconfig
