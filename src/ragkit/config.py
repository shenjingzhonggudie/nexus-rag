from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ragkit.errors import ConfigError


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """检索阶段配置。"""

    top_k: int = Field(default=20, gt=0)
    final_k: int = Field(default=5, gt=0)
    fusion: Literal["rrf", "weighted"] = "rrf"
    sparse_enabled: bool = True
    dense_enabled: bool = True
    rerank_enabled: bool = True

    @model_validator(mode="after")
    def validate_top_k(self) -> "RetrievalConfig":
        """top_k 必须大于 final_k。"""
        if self.top_k < self.final_k:
            raise ValueError(f"final_k ({self.final_k}) 不能大于 top_k ({self.top_k})")
        return self


class ChunkingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """文档切分配置。"""

    strategy: Literal["fixed", "recursive"] = "fixed"
    chunk_size: int = Field(default=400, gt=0)
    overlap: int = Field(default=50, ge=0)

    @model_validator(mode="after")
    def validate_overlap(self) -> "ChunkingConfig":
        """重叠长度必须小于分块长度。"""
        if self.overlap >= self.chunk_size:
            raise ValueError(f"overlap ({self.overlap}) 不能大于 chunk_size ({self.chunk_size})")
        return self


class EmbeddingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """向量嵌入配置。"""

    provider: Literal["hashing"] = "hashing"
    dim: int = Field(default=512, gt=0)


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """大语言模型配置；api_key 在后续输出时需要脱敏。"""

    provider: Literal["none", "openai_compatible"] = "none"
    model: str = ""
    api_key: str = ""
    base_url: str = ""


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """RAGKit 应用总配置。"""

    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    data_dir: Path = Path("data")
    index_dir: Path = Path("data/index")


def load_config(path: str | Path | None = None) -> AppConfig:
    if path is None:
        return AppConfig()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"配置文件不存在：{p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if raw is None:
        raw={}
    if not isinstance(raw, dict):
        raise ConfigError(
            f"配置文件顶层必须是键值映射，实际是 {type(raw).__name__}：{p}"
        )
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"配置校验失败：{p}\n{exc}") from exc
