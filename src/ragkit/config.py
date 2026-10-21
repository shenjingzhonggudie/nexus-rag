"""应用配置：定义各阶段的 Pydantic 模型，并合并 YAML 与环境变量后加载。"""

import os
from collections.abc import Mapping 
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ragkit.errors import ConfigError

ENV_PREFIX = "RAG__"
MASK = "******"


class RetrievalConfig(BaseModel):
    """检索阶段的参数，控制召回、融合和重排流程。

    Attributes:
        top_k: 初步召回的候选数量。
        final_k: 融合或重排后最终保留的条数。
        fusion: 多路结果的融合策略（rrf = 等权，weighted = 加权排名融合）。
        fusion_alpha: weighted 融合时第一条腿（BM25）的权重，取值 0~1。
        sparse_enabled: 是否启用关键词或 BM25 等稀疏检索。
        dense_enabled: 是否启用向量相似度等稠密检索。
        rerank_enabled: 是否对召回候选执行二次重排。
    """

    model_config = ConfigDict(extra="forbid")

    top_k: int = Field(default=20, gt=0)  # 初步召回的候选数量。
    final_k: int = Field(default=5, gt=0)  # 经过融合/重排后最终保留的条数。
    fusion: Literal["rrf", "weighted"] = "weighted"  # 多路结果的融合策略（默认加权：α=0.9 BM25 为主）。
    fusion_alpha: float = Field(default=0.9, ge=0.0, le=1.0)  # weighted 融合时 BM25 腿的权重。
    sparse_enabled: bool = True  # 是否启用关键词/BM25 等稀疏检索。
    dense_enabled: bool = True  # 是否启用向量相似度等稠密检索。
    rerank_enabled: bool = False  # 是否对候选二次重排。默认关：消融证明 hashing dense 余弦精排稳定负贡献（见 PROJECT_LAYOUT 评测契约）

    @model_validator(mode="after")
    def validate_top_k(self) -> "RetrievalConfig":
        """验证最终保留数量不超过初步召回数量。

        Returns:
            RetrievalConfig: 验证通过后的当前配置对象。

        Raises:
            ValueError: top_k 小于 final_k 时抛出。
        """
        if self.top_k < self.final_k:
            raise ValueError(f"final_k ({self.final_k}) 不能大于 top_k ({self.top_k})")
        return self


class ChunkingConfig(BaseModel):
    """文档切分阶段的参数。

    Attributes:
        strategy: 文档切分策略。
        chunk_size: 每个文本片段的目标字符数。
        overlap: 相邻片段之间重复的字符数。
    """

    model_config = ConfigDict(extra="forbid")

    strategy: Literal["fixed", "recursive", "heading"] = "heading"  # 文档切分策略（默认按 ## 标题分块，块级标注用）。
    chunk_size: int = Field(default=300, gt=0)  # 每个文本片段的目标长度。
    overlap: int = Field(default=50, ge=0)  # 相邻片段之间重复的字符数。

    @model_validator(mode="after")
    def validate_overlap(self) -> "ChunkingConfig":
        """验证相邻片段重叠长度小于目标分块长度。

        Returns:
            ChunkingConfig: 验证通过后的当前配置对象。

        Raises:
            ValueError: overlap 大于或等于 chunk_size 时抛出。
        """
        if self.overlap >= self.chunk_size:
            raise ValueError(f"overlap ({self.overlap}) 必须小于 chunk_size ({self.chunk_size})")
        return self


class EmbeddingConfig(BaseModel):
    """文本向量化阶段的参数。

    Attributes:
        provider: 向量嵌入实现方式。
        dim: 每个文本向量的维度。
    """

    model_config = ConfigDict(extra="forbid")

    provider: Literal["hashing"] = "hashing"  # 向量嵌入的实现方式。
    dim: int = Field(default=512, gt=0)  # 每个文本向量的维度。


class LLMConfig(BaseModel):
    """生成回答所用的大语言模型参数。

    Attributes:
        provider: LLM 服务类型；none 表示不调用远程服务。
        model: 要调用的模型名称。
        api_key: 服务认证密钥，不应写入普通日志或未脱敏快照。
        base_url: OpenAI 兼容服务的接口地址。
    """

    model_config = ConfigDict(extra="forbid")

    provider: Literal["none", "openai_compatible"] = "none"  # LLM 服务类型。
    model: str = ""  # 要调用的模型名称。
    api_key: str = Field(default="", repr=False)  # 服务认证密钥，输出时需要脱敏。
    base_url: str = ""  # OpenAI 兼容服务的接口地址。


class AppConfig(BaseModel):
    """RAGKit 的总配置，组合检索、切分、向量化和 LLM 配置。

    Attributes:
        retrieval: 检索阶段配置。
        chunking: 文档切分配置。
        embedding: 文本向量化配置。
        llm: 回答生成模型配置。
        data_dir: 原始语料目录（build 的语料来源）。
        index_dir: 检索索引保存目录。
    """

    model_config = ConfigDict(extra="forbid")

    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)  # 检索阶段配置。
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)  # 文档切分配置。
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)  # 向量化配置。
    llm: LLMConfig = Field(default_factory=LLMConfig)  # 回答生成模型配置。
    data_dir: Path = Path("data/raw")  # 原始语料目录。
    index_dir: Path = Path("data/index")  # 检索索引保存目录。

    def snapshot(self) -> dict:
        """生成适合展示或保存的配置快照，并掩码 API 密钥。

        Returns:
            dict: JSON 兼容的配置字典；api_key 非空时替换为 MASK，空值保留为空串。
        """
        d = self.model_dump(mode="json")
        d["llm"]["api_key"] = MASK if d["llm"]["api_key"] else ""
        return d


def _deep_merge(
    base: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    """递归合并配置字典，覆盖值优先且不修改输入对象。

    Args:
        base: 基础配置，通常来自 YAML 文件。
        overrides: 覆盖配置，通常来自环境变量解析结果。

    Returns:
        dict[str, Any]: 深拷贝并合并后的新配置字典；仅当双方同名值都是字典时
            才递归合并，否则由 overrides 的值整体覆盖。
    """
    result = deepcopy(base)
    for key, value in overrides.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result



def _collect_env_overrides(
    environ: Mapping[str, str], prefix: str = ENV_PREFIX
) -> dict[str, Any]:
    """收集环境变量中的配置覆盖项，默认前缀为 RAG__。

    命名规则（段数不包含前缀）：
    - RAG__<字段>：顶层字段，如 RAG__DATA_DIR=mydata。
    - RAG__<段>__<字段>：一层嵌套字段，如 RAG__RETRIEVAL__TOP_K=30。
    - 段数 >= 3、只有前缀或包含空段：忽略，如 RAG__A__B__C、RAG__。
      环境变量空间是共享的，不对不支持的命名格式报错。

    段名和字段名一律转小写，值保留为字符串供后续模型校验。
    格式合法但字段名拼错时不能忽略：RAG__RETRIEVAL__TOPKK=30
    会生成 {"retrieval": {"topkk": "30"}}。本函数不校验字段名；
    后续应由 extra="forbid" 拒绝未知字段，并由加载层将 ValidationError
    包装为 ConfigError。

    Args:
        environ: 环境变量名称和值的映射。
        prefix: 用于筛选配置环境变量的前缀，默认是 RAG__。

    Returns:
        dict[str, Any]: 按字段路径嵌套的覆盖字典；值仍为字符串，留待 Pydantic
            转换和校验。
    """
    overrides = {}
    for key, value in environ.items():
        if key.startswith(prefix):
            # 将 RAG__retrieval__top_k 转换为 ['retrieval', 'top_k']
            path = key[len(prefix) :].lower().split("__")
            if len(path) > 2 or not all(path):
                continue
            d = overrides
            for p in path[:-1]:
                d = d.setdefault(p, {})
            d[path[-1]] = value
    return overrides


def load_config(
    path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    """读取 YAML 配置、合并环境变量覆盖并校验为应用配置。

    Args:
        path: YAML 配置文件路径；None 表示只使用默认配置和环境变量。
        environ: 环境变量映射；None 时读取当前进程的 os.environ。

    Returns:
        AppConfig: 合并并通过 Pydantic 校验的应用配置。

    Raises:
        FileNotFoundError: path 指向的配置文件不存在。
        ConfigError: YAML 顶层不是映射，或合并后的配置未通过模型校验。
        OSError: 配置文件存在但无法读取时由 pathlib 传播。
    """
    if path is None:
        base={}
    else:
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
        base = raw

    if environ is None:
        environ = os.environ

    overrides = _collect_env_overrides(environ)
    merged = _deep_merge(base, overrides)

    try:
        return AppConfig.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(f"配置校验失败：{path or '<无配置文件，仅环境变量覆盖>'}\n{exc}") from exc