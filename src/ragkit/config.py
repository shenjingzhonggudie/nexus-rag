from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ragkit.errors import ConfigError


class RetrievalConfig(BaseModel):
    """检索阶段的参数：控制召回、融合和重排流程。"""

    model_config = ConfigDict(extra="forbid")

    top_k: int = Field(default=20, gt=0)  # 初步召回的候选数量。
    final_k: int = Field(default=5, gt=0)  # 经过融合/重排后最终保留的条数。
    fusion: Literal["rrf", "weighted"] = "rrf"
    sparse_enabled: bool = True  # 是否启用关键词/BM25 等稀疏检索。
    dense_enabled: bool = True  # 是否启用向量相似度等稠密检索。
    rerank_enabled: bool = True  # 是否启用对候选结果的二次重排。

    @model_validator(mode="after")
    def validate_top_k(self) -> "RetrievalConfig":
        """top_k 必须大于 final_k。"""
        if self.top_k < self.final_k:
            raise ValueError(f"final_k ({self.final_k}) 不能大于 top_k ({self.top_k})")
        return self


class ChunkingConfig(BaseModel):
    """文档切分阶段的参数。"""

    model_config = ConfigDict(extra="forbid")

    strategy: Literal["fixed", "recursive"] = "fixed"  # 文档切分策略。
    chunk_size: int = Field(default=400, gt=0)  # 每个文本片段的目标长度。
    overlap: int = Field(default=50, ge=0)  # 相邻片段之间重复的字符数。

    @model_validator(mode="after")
    def validate_overlap(self) -> "ChunkingConfig":
        """重叠长度必须小于分块长度。"""
        if self.overlap >= self.chunk_size:
            raise ValueError(f"overlap ({self.overlap}) 不能大于 chunk_size ({self.chunk_size})")
        return self


class EmbeddingConfig(BaseModel):
    """文本向量化阶段的参数。"""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["hashing"] = "hashing"  # 向量嵌入的实现方式。
    dim: int = Field(default=512, gt=0)  # 每个文本向量的维度。


class LLMConfig(BaseModel):
    """生成回答所用的大语言模型参数。"""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["none", "openai_compatible"] = "none"  # LLM 服务类型。
    model: str = ""  # 要调用的模型名称。
    api_key: str = ""  # 服务认证密钥，输出时需要脱敏。
    base_url: str = ""  # OpenAI 兼容服务的接口地址。


class AppConfig(BaseModel):
    """RAGKit 的总配置，组合检索、切分、向量化和 LLM 配置。"""

    model_config = ConfigDict(extra="forbid")

    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)  # 检索阶段配置。
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)  # 文档切分配置。
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)  # 向量化配置。
    llm: LLMConfig = Field(default_factory=LLMConfig)  # 回答生成模型配置。
    data_dir: Path = Path("data")  # 原始数据和中间文件目录。
    index_dir: Path = Path("data/index")  # 检索索引保存目录。


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
