# 项目文件清单

> 生成日期：2026-10-03（最后更新：2026-10-14）
> 用途：随时回答"现在有哪些文件、各自负责什么、对外契约是什么"
> 项目根目录：`C:\Users\王佳浩\Desktop\项目`

## 一、当前目录树（真实状态）

```text
项目/
├── .git/                      # git 仓库（已 4 次提交，最后一次 586d549 / 2026-10-09；loaders 起多轮未提交）
├── .vscode/                   # 编辑器配置
├── .venv/                     # Python 3.12 虚拟环境（不入 git；基准解释器 = 系统 Python312）
├── .pytest_cache/             # pytest 缓存（不入 git）
├── .gitignore                 # 忽略 .venv/ __pycache__/ *.egg-info/ .pytest_cache/ .env
├── pyproject.toml             # 构建配置、元信息、CLI 入口点、pytest 配置；依赖 pyyaml + pydantic
├── README.md                  # 定位 / 当前状态 / 快速开始 / 目录结构 / 常见问题 / 路线图
├── LEARNING_LOG.md            # 逐轮学习记录（问题、根因、通用知识、技术债）
├── PROJECT_LAYOUT.md          # 本文件：文件清单与契约
├── configs/
│   └── default.yaml           # 默认配置模板（值必须与模型默认值一致）
├── data/                      # 【第 18~19 轮】真实语料与评测数据
│   ├── raw/                   # 语料：100 篇中文技术文档（20 正 + 80 误导，脚本生成，.md）
│   └── eval/qrels.json        # 评测集：300 条 query + 相关文档标注
├── src/
│   └── ragkit/
│       ├── __init__.py        # 包 docstring + __version__ = "0.0.1"
│       ├── cli.py             # 【第 16 轮】命令行：build / ask 子命令 + --version（薄壳，零业务逻辑）
│       ├── schemas.py         # 领域模型（7 个）+ 序列化方法
│       ├── config.py          # 配置模型（5 个）+ YAML 加载 + 环境变量覆盖 + 脱敏快照
│       ├── errors.py          # RagkitError / ConfigError / LoadError（带 path/reason/error_type）
│       ├── text/              # 【第 6 轮】文本层
│       │   ├── __init__.py    # 公开 normalize_text / tokenize / tokenize_terms / tokenize_bigrams
│       │   ├── normalize.py   # 换行统一、零宽与控制字符删除、NFKC、空白清理、空行折叠
│       │   └── tokenize.py    # jieba 精确模式词元 + 相邻汉字 bigram（含 CJK 区间表）
│       ├── loaders/           # 【第 7 轮】加载层
│       │   ├── __init__.py    # 公开 load_file / load_dir / LoadFailure / LoadReport
│       │   ├── report.py      # LoadFailure、LoadReport（纯数据，暂不序列化）
│       │   ├── files.py       # 单文件：字节 → 哈希 → 解码回退 → 提标题 → Document
│       │   └── directory.py   # load_dir：递归、稳定排序、跳过隐藏路径、错误隔离
│       ├── chunking/          # 【第 8 轮】分块层
│       │   ├── __init__.py    # 公开 chunk_document / iter_spans / make_chunk_id
│       │   ├── fixed.py       # iter_spans：窗口 + 边界对齐 + overlap + 触底收尾
│       │   ├── ids.py         # make_chunk_id：稳定 ID 规则
│       │   └── document.py    # chunk_document：规范化 → 切分 → 计数 → 组装 Chunk
│       ├── embeddings/        # 【第 9 轮】向量化层
│       │   ├── __init__.py    # 公开 embed_text
│       │   └── hashing.py     # 特征哈希：token → 下标/符号 → 词频累加 → L2 归一化
│       ├── stores/            # 【第 10 轮】向量库层
│       │   ├── __init__.py    # 公开 write / load / VectorStore
│       │   └── vector_store.py # 三元组同序、原子落盘、加载校验
│       ├── retrieval/         # 【第 11~13 轮】检索层
│       │   ├── __init__.py    # 公开 BM25Index / dense_search / rrf_fuse / weighted_fuse / rerank / search / RetrievalResult
│       │   ├── bm25.py        # BM25Index：建统计 + 打分
│       │   ├── dense.py       # dense_search：向量点积召回（余弦相似度）
│       │   ├── fusion.py      # rrf_fuse / weighted_fuse：等权 RRF 与加权排名融合
│       │   ├── rerank.py      # rerank：dense 余弦精排，输出 final_k
│       │   ├── pipeline.py    # search：编排召回→融合→重排，生成 trace
│       │   └── result.py      # RetrievalResult：最终结果 + 检索轨迹
│       ├── index/            # 【第 14 轮】建库层
│       │   ├── __init__.py    # 公开 build / load_index / BuiltIndex / write_chunks / read_chunks
│       │   ├── assets.py      # BuiltIndex：检索就绪资源容器
│       │   ├── chunks_store.py # chunks.jsonl 读写（JSONL，原子替换）
│       │   └── builder.py     # build / load_index 编排
│       ├── generation/        # 【第 15 轮】生成层
│       │   ├── __init__.py    # 公开 answer_question
│       │   └── answer.py     # answer_question：证据→引用、拒答判定、抽取式回答
│       ├── api/              # 【第 17 轮】HTTP API 层
│       │   ├── __init__.py    # 公开 create_server / make_handler
│       │   └── server.py     # 壳芯分离：_answer_payload 纯芯 + handler HTTP 细节 + 错误翻译表
│       ├── evaluation/       # 【第 18~19 轮】评测层
│       │   ├── __init__.py    # 公开 recall_at_k / mrr / load_qrels / evaluate / run_ablation
│       │   ├── metrics.py     # recall_at_k / mrr 纯函数
│       │   ├── qrels.py       # Qrel / load_qrels：评测集加载与校验
│       │   ├── report.py      # evaluate：编排 + doc_id 去重 + 冷/热耗时表
│       │   └── ablation.py    # run_ablation：4 组单变量对照 + 边际贡献
│       └── ragkit.egg-info/   # editable 安装产物（不入 git）
└── tests/
    ├── test_smoke.py             # 3 条冒烟测试
    ├── test_schemas.py           # 36 条模型测试
    ├── test_config.py            # 25 条配置测试
    ├── test_text_normalize.py    # 9 条规范化测试
    ├── test_text_tokenize.py     # 9 条分词测试
    ├── test_loaders.py           # 15 条加载测试
    ├── test_chunking_fixed.py    # 28 条切分测试
    ├── test_chunking_document.py # 8 条组装与 metadata 契约测试
    ├── test_chunking_ids.py      # 8 条 chunk_id 契约测试
    ├── test_embeddings_hashing.py # 14 条 embedding 契约测试
    ├── test_vector_store.py      # 14 条向量库契约测试
    ├── test_bm25.py              # 11 条 BM25 契约测试
    ├── test_dense.py             # 9 条 dense 契约测试
    ├── test_fusion.py            # 12 条融合契约测试（RRF + 加权融合）
    ├── test_rerank.py            # 8 条重排契约测试
    ├── test_pipeline.py          # 9 条流水线契约测试
    ├── test_index_build.py       # 7 条建库契约测试
    ├── test_index_load.py        # 5 条索引加载契约测试
    ├── test_generation.py        # 6 条生成层契约测试
    ├── test_cli.py               # 11 条 CLI 契约测试
    ├── test_api.py               # 12 条 HTTP API 契约测试
    ├── test_metrics.py           # 8 条指标契约测试
    └── test_evaluation.py        # 3 条评测编排契约测试
```

## 二、文件职责与来源

| 文件 | 职责 | 产生于 |
|---|---|---|
| `pyproject.toml` | 声明 src 布局（`where = ["src"]`）、CLI 入口点、pytest 配置 | 第 0 课 |
| `src/ragkit/__init__.py` | 包标识 + 版本号 | 第 0 课 |
| `src/ragkit/cli.py` | `main(argv=None, environ=None) -> int`；`ragkit build` / `ask` / `serve` / `eval` 四子命令；薄壳，领域层延迟 import | 第 0 课；第 16~18 轮 |
| `src/ragkit/api/server.py` | `create_server` / `make_handler` / `_answer_payload`：壳芯分离、错误翻译表、请求日志 | 第 17 轮 |
| `src/ragkit/evaluation/metrics.py` | `recall_at_k` / `mrr`：检索质量指标纯函数 | 第 18 轮 |
| `src/ragkit/evaluation/qrels.py` | `Qrel` / `load_qrels`：评测集加载与校验 | 第 18 轮 |
| `src/ragkit/evaluation/report.py` | `evaluate`：评测编排 + doc_id 去重 + 冷/热耗时表 | 第 18 轮 |
| `src/ragkit/evaluation/ablation.py` | `run_ablation`：4 组单变量对照 + 边际贡献 | 第 19 轮 |
| `src/ragkit/schemas.py` | 领域模型与 `to_dict` / `from_dict` | 第 1~3 轮 |
| `src/ragkit/config.py` | 配置模型、YAML 加载、环境变量覆盖、深合并、脱敏快照 | 第 4~5 轮 |
| `src/ragkit/errors.py` | `RagkitError`、`ConfigError`、`LoadError`（三字段：path / reason / error_type） | 第 4、7 轮 |
| `configs/default.yaml` | 默认配置模板 | 第 4 轮 |
| `src/ragkit/text/normalize.py` | `normalize_text(text) -> str`，清洗的唯一入口 | 第 6 轮 |
| `src/ragkit/text/tokenize.py` | `tokenize_terms` / `tokenize_bigrams` / `tokenize` | 第 6 轮 |
| `src/ragkit/loaders/files.py` | 单文件 → `Document`：编码回退、标题提取、五键 metadata | 第 7 轮 |
| `src/ragkit/loaders/directory.py` | `load_dir`：遍历、稳定排序、单文件错误隔离 | 第 7 轮 |
| `src/ragkit/loaders/report.py` | `LoadFailure` / `LoadReport`（运行期对象） | 第 7 轮 |
| `src/ragkit/chunking/fixed.py` | `iter_spans`：窗口切分 + 边界对齐 + overlap + 触底收尾 | 第 8 轮 |
| `src/ragkit/chunking/ids.py` | `make_chunk_id`：稳定 ID | 第 8 轮 |
| `src/ragkit/chunking/document.py` | `chunk_document`：规范化 → 切分 → 计数 → `Chunk` | 第 8 轮 |
| `src/ragkit/embeddings/hashing.py` | `embed_text`：token 特征哈希 + 词频累加 + L2 归一化 | 第 9 轮 |
| `src/ragkit/stores/vector_store.py` | `VectorStore` + `write` / `load`：三元组同序、原子落盘、加载校验 | 第 10 轮 |
| `src/ragkit/retrieval/bm25.py` | `BM25Index`：建索引统计 df / 词频 / 块长，`search` 打分 | 第 11 轮 |
| `src/ragkit/retrieval/dense.py` | `dense_search`：embed query → 矩阵点积 → argsort 取 top_k | 第 12 轮 |
| `src/ragkit/retrieval/fusion.py` | `rrf_fuse`（等权）/ `weighted_fuse`（加权 S=α·S1+(1-α)·S2）：按 chunk_id 聚合、rank 分累加 | 第 12 轮；第 23 轮加权 |
| `src/ragkit/retrieval/rerank.py` | `rerank`：dense 余弦精排，输出 final_k，sub_scores 记 prev | 第 13 轮 |
| `src/ragkit/retrieval/pipeline.py` | `search`：编排召回→融合→重排，生成 RetrievalTrace | 第 13 轮 |
| `src/ragkit/retrieval/result.py` | `RetrievalResult`：最终结果 + 检索轨迹 | 第 13 轮 |
| `src/ragkit/index/assets.py` | `BuiltIndex`：bm25 / store / id_to_chunk / dim / failures 打包 | 第 14 轮 |
| `src/ragkit/index/chunks_store.py` | `write_chunks` / `read_chunks`：chunks.jsonl 读写（坏行报错带行号） | 第 14 轮 |
| `src/ragkit/index/builder.py` | `build` / `load_index`：建库编排与索引加载 | 第 14 轮 |
| `src/ragkit/generation/answer.py` | `answer_question`：证据→引用、拒答判定、抽取式回答 | 第 15 轮 |
| `tests/test_smoke.py` | 包可导入、CLI 可调用、退出码正确 | 第 0 课 |
| `tests/test_schemas.py` | 7 个模型的往返、契约、校验、兼容性 | 第 1~3 轮 |
| `tests/test_config.py` | 配置默认值、校验、环境变量覆盖、脱敏、测试隔离 | 第 4~5 轮 |
| `tests/test_text_normalize.py` | 规范化 5 步顺序、幂等性、中文标点保留 | 第 6 轮 |
| `tests/test_text_tokenize.py` | 词元过滤、bigram 相邻性、URL/版本号、双通道合并 | 第 6 轮 |
| `tests/test_loaders.py` | 坏文件隔离、编码回退、相对路径坐标系、排序、cwd 无关 | 第 7 轮 |
| `tests/test_chunking_fixed.py` | 参数校验、边界选择（11 条参数化）、重叠、小输入穷举不变式 | 第 8 轮 |
| `tests/test_chunking_document.py` | 偏移不变式、metadata 四键、重复序号、空文本、参数校验 | 第 8 轮 |
| `tests/test_chunking_ids.py` | ID 格式、稳定、局部、唯一 | 第 8 轮 |
| `tests/test_embeddings_hashing.py` | 长度、归一化、确定性、跨进程稳定、相似度排序、空 token、参数校验 | 第 9 轮 |
| `tests/test_vector_store.py` | 三元组同序往返、原子落盘、加载校验（dim/行数/损坏）、空库、可复现 | 第 10 轮 |
| `tests/test_bm25.py` | 手算样例、词频/罕见词/长度三直觉、k1/b 参数化、空 query/语料、stage/top_k、query 规范化、确定性 | 第 11 轮 |
| `tests/test_dense.py` | 点积降序、score 纯 float、stage、top_k、同文本余弦=1、空 query/空 store、确定性 | 第 12 轮 |
| `tests/test_fusion.py` | 跨腿聚合累加、去重、保留 Chunk 对象、单腿退化、空腿容错、top_k、k 常数、加权融合 α 权重/极端值/单腿退化 | 第 12 轮；第 23 轮加权 |
| `tests/test_rerank.py` | 手算样例、final_k 截断、stage、sub_scores.prev、空候选、不在库候选丢弃、确定性 | 第 13 轮 |
| `tests/test_pipeline.py` | 开关组合（只稀疏/只稠密/都关/关重排）、trace 阶段顺序与候选数口径、返回类型 | 第 13 轮 |
| `tests/test_index_build.py` | 五文件产物、id 三方一致、坏文件隔离、空目录、可直接检索、可复现 | 第 14 轮 |
| `tests/test_index_load.py` | 与 build 结果等价、缺文件 / id 不一致 / 坏行拦截 | 第 14 轮 |
| `tests/test_generation.py` | 正常组装、引用编号、拒答（trace 仍挂）、fail-fast、序列化、端到端链路 | 第 15 轮 |
| `README.md` | 项目说明与复现步骤（四命令 / 架构分层 / 评测消融结论） | 第 0 课；第 21 轮重写 |
| `LEARNING_LOG.md` | 逐轮记录：问题、根因、通用知识、技术债 | 第 3 轮末 |
| `PROJECT_LAYOUT.md` | 本文件 | 第 3 轮末 |

## 三、模型与序列化契约（最重要的一节）

**契约 = `to_dict()` 的键集合。** 它决定了第 5 阶段 JSONL 的格式、第 8 阶段 manifest 的字段、第 12 阶段 API 响应的形状。任何键名的改动都是破坏性变更。

### `Document`

| 字段 | 类型 | 必填 | 默认值 |
|---|---|---|---|
| `doc_id` | `str` | 是 | — |
| `source` | `str` | 是 | — |
| `text` | `str` | 是 | — |
| `title` | `str` | 否 | `""` |
| `metadata` | `dict[str, Any]` | 否 | `field(default_factory=dict)` |

**to_dict 键集合**：`doc_id`、`source`、`text`、`title`、`metadata`
**已知约定**：`to_dict` 返回的 `metadata` 与对象共享同一字典对象，调用方不得修改其内容

### `Chunk`

| 字段 | 类型 | 必填 | 默认值 |
|---|---|---|---|
| `chunk_id` | `str` | 是 | — |
| `doc_id` | `str` | 是 | — |
| `text` | `str` | 是 | — |
| `ordinal` | `int` | 是 | — |
| `score_hint` | `float` | 否 | `0.0` |
| `title` | `str` | 否 | `""` |
| `source` | `str` | 否 | `""` |
| `metadata` | `dict[str, Any]` | 否 | `field(default_factory=dict)` |

**to_dict 键集合**：`chunk_id`、`doc_id`、`text`、`ordinal`、`score_hint`、`title`、`source`、`metadata`
**已知约定**：`metadata` 为引用共享；`score_hint` 为后来新增的可选字段（用于验证"旧 JSONL 仍可加载"）

### `ScoredChunk`

| 字段 | 类型 | 必填 | 默认值 |
|---|---|---|---|
| `chunk` | `Chunk` | 是 | — |
| `score` | `float` | 是 | — |
| `stage` | `str` | 是 | — |
| `sub_scores` | `dict[str, float]` | 否 | `field(default_factory=dict)` |

**to_dict 键集合**：`chunk`、`score`、`stage`、`sub_scores`
**嵌套处理**：`chunk` 递归降级为字典，`from_dict` 递归升格为 `Chunk` 对象

### `Citation`

| 字段 | 类型 | 必填 | 默认值 |
|---|---|---|---|
| `index` | `int` | 是 | — |
| `source` | `str` | 是 | — |
| `snippet` | `str` | 是 | — |
| `title` | `str` | 否 | `""` |

**to_dict 键集合**：`index`、`source`、`snippet`、`title`

### `StageTrace`

| 字段 | 类型 | 必填 | 默认值 |
|---|---|---|---|
| `name` | `str` | 是 | — |
| `latency_ms` | `float` | 否 | `0.0` |
| `candidate_count` | `int` | 否 | `0` |

**to_dict 键集合**：`name`、`latency_ms`、`candidate_count`

### `RetrievalTrace`

| 字段 | 类型 | 必填 | 默认值 |
|---|---|---|---|
| `stages` | `list[StageTrace]` | 否 | `field(default_factory=list)` |

**to_dict 键集合**：`stages`
**额外方法**：`total_latency_ms() -> float`（各阶段耗时求和；不设冗余字段）
**加载策略**：`stages` 缺失或为 `None`（JSON `null`）时按空列表处理

### `Answer`

| 字段 | 类型 | 必填 | 默认值 |
|---|---|---|---|
| `question` | `str` | 是 | — |
| `answer` | `str` | 是 | — |
| `citations` | `list[Citation]` | 否 | `field(default_factory=list)` |
| `refused` | `bool` | 否 | `False` |
| `confidence` | `float` | 否 | `0.0` |
| `contexts` | `list[str]` | 否 | `field(default_factory=list)` |
| `trace` | `RetrievalTrace \| None` | 否 | `None` |

**to_dict 键集合**：`question`、`answer`、`citations`、`refused`、`confidence`、`contexts`、`trace`
**已知约定**：
- 拒答时 `refused=True`，`answer` 为空串，`citations` 为空列表
- `contexts` 是纯字符串列表，不是 `Chunk` 列表
- `trace=None` 表示没有检索轨迹（拒答或未运行流水线），序列化保留为 `null`
- 加载时 `citations` / `contexts` 缺失或为 `None` 按空处理

## 四、配置契约（`config.py`）

配置的契约 = **字段名 + 默认值 + 约束**，以及**环境变量的映射规则**。与领域模型不同：配置文件是人手写的，所以**未知键必须报错**（`extra="forbid"` 逐模型生效）。

### 环境变量映射规则

| 形式 | 含义 | 例子 |
|---|---|---|
| `RAG__<字段>` | 顶层字段 | `RAG__DATA_DIR=mydata` |
| `RAG__<段>__<字段>` | 一层嵌套字段 | `RAG__RETRIEVAL__TOP_K=30` |
| 段数 ≥ 3 或只有前缀 | **忽略**（环境变量空间是共享的，不报错） | `RAG__A__B__C` |
| 格式合法但字段名不存在 | **报错** `ConfigError` | `RAG__RETRIEVAL__TOPKK=30` |

**优先级**：默认值 < YAML < 环境变量；合并方式为**递归深合并**（不是 `dict.update()`）。
**类型转换**：环境变量值永远是字符串，一律交给 Pydantic 转换与校验，不自己写 `int()` / `bool()`。

### 五个模型

| 模型 | 字段（默认值 / 约束） |
|---|---|
| `RetrievalConfig` | `top_k=20 (gt 0)`、`final_k=5 (gt 0 且 ≤ top_k)`、`fusion="weighted"`（默认加权，`fusion_alpha=0.9` 即 BM25 权重 0.9 / dense 权重 0.1）、`sparse_enabled=True`、`dense_enabled=True`、`rerank_enabled=False`（**默认关：dense 余弦精排负贡献**） |
| `ChunkingConfig` | `strategy="fixed"`、`chunk_size=400 (gt 0)`、`overlap=50 (ge 0 且 < chunk_size)` |
| `EmbeddingConfig` | `provider="hashing"`、`dim=512 (gt 0)` |
| `LLMConfig` | `provider="none"`、`model=""`、`api_key="" (repr=False)`、`base_url=""` |
| `AppConfig` | 上面四个（`default_factory`）+ `data_dir=Path("data/raw")`、`index_dir=Path("data/index")` |

### 脱敏契约

`AppConfig.snapshot() -> dict`：

- 用 `model_dump(mode="json")` 取得纯基础类型（`Path` → 字符串，可直接进 JSON）；
- `api_key` **非空**时替换为掩码 `"******"`，为空则保持 `""`；
- `api_key` 字段带 `Field(repr=False)`，`repr(cfg)` 同样不泄漏。

**验收判据**：`"<原文>" not in json.dumps(snapshot)`，以及 `"<原文>" not in repr(cfg)`。

### 错误类型

| 情况 | 抛什么 |
|---|---|
| 路径不存在 | `FileNotFoundError`（标准异常） |
| 文件顶层不是映射 | `ConfigError` |
| Pydantic 校验失败（类型 / 取值 / 未知键 / 跨字段） | `ValidationError` 包装成 `ConfigError`，用 `raise ... from exc` 保留堆栈 |

## 五、文本层契约（`text/`）

**导入方式**：`from ragkit.text import normalize_text, tokenize, tokenize_terms, tokenize_bigrams`

### 处理链

```
原始文本
  └─ normalize_text          清洗（所有下游都从这一步之后开始）
       ├─ tokenize_terms     jieba 精确模式 → 过滤无有效内容的词元
       └─ tokenize_bigrams   相邻汉字双字组合
  └─ tokenize = tokenize_terms(...) + tokenize_bigrams(...)   # 两个通道直接拼接
```

### `normalize_text` 的 5 步固定顺序

| 步 | 做什么 | 例子 |
|---|---|---|
| 1 | 统一换行：`\r\n`、`\r` → `\n` | — |
| 2 | 删除零宽字符与控制字符（**保留 `\n`、`\t`**）：U+200B–200D、U+FEFF、C0/C1 控制符、DEL | `a\u200bb` → `ab` |
| 3 | NFKC 归一 | `ＡＢＣ１２３，：` → `ABC123,:` |
| 4 | 逐行 `rstrip()`，行内制表符 → 单个空格 | `a\tb ` → `a b` |
| 5 | 连续空行折叠为**最多一个**空行 | `a\n\n\n\nb` → `a\n\nb` |

**幂等性**：`normalize_text(normalize_text(x)) == normalize_text(x)`（有测试锁住）
**明确不做**：不去标点、不改大小写、不删换行、不切句（切句属第 9 阶段）
**NFKC 的边界**：它会改全角 ASCII，但**不改**中文标点 `。、；`（有测试锁住）

### `tokenize_terms(text) -> list[str]`

- 内部先 `normalize_text`，再 `jieba.cut(text, cut_all=False)`；
- 过滤规则：词元中**至少有 1 个**汉字 / ASCII 字母 / 数字（`str.isdigit()`，含非 ASCII 数字）；纯空白、纯标点被丢弃；
- **保留**：单字词、数字、URL 片段（`https`）、版本号（`v2.1`、`3`、`python3.12`）、重复词；
- 顺序 = jieba 输出顺序。

### `tokenize_bigrams(text) -> list[str]`

- 对规范化文本取相邻字符对，**左右都必须是汉字**才产出；
- 不跨越非汉字：`中 文` 不产生 `中文`；ASCII 文本返回空列表；
- 可重叠：`中文分词` → `中文`、`文分`、`分词`。

### `tokenize(text) -> list[str]`

- = `tokenize_terms(normalized) + tokenize_bigrams(normalized)`；
- **不排序、不去重、不交错**：先全部词元，再全部 bigram → **不代表原文位置**；同一个词可能同时出现在两部分。

### 供第 6 阶段（BM25）使用的约定

- `tokenize()` 输出**保留重复项**，词频（TF）由调用方统计，不在 `tokenize` 内去重；
- 汉字区间表 `_CJK_RANGES` 是私有的，覆盖基本区 + 扩展区 A~I；**不含**假名、韩文音节、中文标点；
- 三个函数对空输入统一返回空列表。

### 实测：首次调用的隐藏成本（2026-10-09 实测）

```
首次执行 tokenize(...)：jieba 在 stderr 打印
  Building prefix dict from the default dictionary ... / Loading model from cache ... / Loading model cost 1.775 seconds.
首次耗时约 1.8 秒，之后走内存词典
```

两个后果，第 11~13 阶段会撞上：
- **延迟统计会被首次调用污染**：冷启动的 P95 里会混进这 1.8 秒 → 做性能表时必须区分冷/热，或先预热一次；
- **stderr 有噪声**：CLI / API 日志里会出现 jieba 的自述文字 → 结构化日志前要处理。

## 六、加载层契约（`loaders/`）

**导入方式**：`from ragkit.loaders import load_file, load_dir, LoadFailure, LoadReport`

### 公开 API

| 接口 | 签名 | 失败时的行为 |
|---|---|---|
| `load_file` | `(path: Path, *, source: str \| None = None) -> Document` | 抛 `LoadError`（带 path / reason / error_type） |
| `load_dir` | `(root: Path, *, suffixes=( ".txt", ".md", ".markdown")) -> LoadReport` | 见"两类错误" |

### 两类错误（这一层的核心区分）

| 错误性质 | 例子 | 行为 |
|---|---|---|
| **配置 / 参数错误** | `root` 不存在或不是目录 | **立刻抛** `FileNotFoundError` |
| **数据问题** | 单个文件编码解不开、无权限 | 记一条 `LoadFailure`，**继续处理其余文件** |

单文件失败**只隔离** `OSError` 与 `UnicodeDecodeError`；`TypeError` / `AttributeError` 这类自身缺陷必须直接抛出——否则会被伪装成"坏文件"静默跳过。

### 编码与路径口径

| 项 | 规则 |
|---|---|
| 解码顺序 | `utf-8-sig` → 失败回退 `gbk` → 都失败才算失败 |
| `metadata["encoding"]` | 记"**编码家族**"（`utf-8` / `gbk`），不是 codec 名 `utf-8-sig`；理由见 `load_file` docstring（契约要稳定、实现可变；BOM 有无已由 `size` 与 `content_hash` 体现） |
| `source` / `metadata["path"]` | **同一坐标系**：相对 `root` 的 POSIX 路径（正斜杠），绝不写绝对路径 |
| `LoadFailure.path` | 同上坐标系；而 `LoadError.path` 保留调用方原样传入的路径，仅供人类定位 |

### `Document.metadata` 五键（契约）

| 键 | 含义 |
|---|---|
| `path` | 相对 root 的 POSIX 路径，恒等于 `source` |
| `size` | 原始字节数（含 BOM），来自**实际读到的那份字节**，不是 `stat()` |
| `ext` | 小写扩展名（含前导点） |
| `encoding` | 编码家族（`utf-8` / `gbk`） |
| `content_hash` | `sha256(原始字节).hexdigest()[:16]`（64 bit） |

**明确不放 `mtime`**：同一输入必须产出同样的 `Document`；变更检测用内容哈希，不用时间戳。

### 遍历与标题规则

- 递归遍历；按白名单后缀过滤（**大小写不敏感**）；**跳过任何以 `.` 开头的路径段**；结果**按 `source` 排序**（两次运行顺序必须一致）；
- `title`：Markdown 取首个标题行（`#` 开头，允许 0~3 前导空格、1~6 个 `#`，去掉结尾闭合 `#`）；否则回退为不含扩展名的文件名；
- **提取标题不修改 `text`**——标题行保留在正文里，避免证据缺失。

## 七、分块层契约（`chunking/`）

**导入方式**：`from ragkit.chunking import chunk_document, iter_spans, make_chunk_id`

### 公开 API

| 接口 | 签名 |
|---|---|
| `iter_spans` | `(text: str, *, chunk_size: int, overlap: int) -> list[tuple[int, int]]` |
| `make_chunk_id` | `(doc_id: str, text: str, occurrence: int) -> str` |
| `chunk_document` | `(document: Document, *, chunk_size: int = 400, overlap: int = 50) -> list[Chunk]` |

### `iter_spans` 的规则（不可随手改）

| 规则 | 内容 |
|---|---|
| 分块单位 | **字符**（Unicode 码点）。绝不能改成 jieba 词数或 token 数——那些依赖第三方库版本，一变则全部 `chunk_id` 改变、索引全量失效 |
| 参数校验 | `chunk_size <= 0`、`overlap < 0`、`overlap >= chunk_size` → `ValueError`（**配置层与函数层各拦一次**） |
| 边界优先级 | **类型优先于位置**：先看 `\n\n`，有就用（哪怕更靠后的单换行更接近窗口末尾）；否则 `\n`；否则 `。！？；`。边界字符**归属前一块** |
| 回退下限 | 切点不得早于 `start + chunk_size // 2`，否则硬切 |
| **触底收尾** | 窗口触到文末（剩余 ≤ `chunk_size`）时**不再找边界，整段收尾**。"短文本单块"是它的自然推论，无需特判 |
| 前进保底 | `next_start = max(end - overlap, start + 1)`——保证起点严格递增（只靠回退下限挡不住 `overlap` 接近 `chunk_size` 的情形） |
| 不变式 | 每段 `0 < end - start <= chunk_size`；并集 == `[0, len(text))`；空输入返回 `[]` |

### `chunk_id` 的规则（契约，改动即破坏性变更）

```
chunk_id = f"{doc_id}#{sha256(chunk.text).hexdigest()[:8]}@{occurrence}"
例：docs/faq.md#3f2a1b9c@1
```

| 性质 | 含义 | 靠什么保证 |
|---|---|---|
| 稳定 | 同输入两次 → ID 逐字相同 | 只依赖 `doc_id` + 块文本 + 重复序号 |
| **局部** | 内容未变的块，位置移动后 ID 也不变 | **ID 里不放 `ordinal` / 偏移** |
| 唯一 | 同文档内不重复 | `occurrence`（用**完整 sha256** 计数，仅在展示时截断 8 位） |

### `Chunk.metadata` 四键（契约）

| 键 | 含义 |
|---|---|
| `strategy` | 分块策略名（当前 `"fixed"`）；第 14 阶段消融实验靠它归因 |
| `char_start` / `char_end` | 相对**规范化后**文本的半开区间 |
| `content_hash` | `chunk.text` 的 sha256 前 16 位 |

**为什么故意不复制 `Document.metadata` 进来**：`content_hash` 两边同名但**不同义**（Document 的是原始字节、Chunk 的是块文本）→ 同键两义；且 `path` 与 `Chunk.source` 冗余、`title`/`source` 已是独立字段；目前也没有任何模块读 metadata。

### 不变式与已知行为

- `chunk.text == normalize_text(document.text)[char_start:char_end]`（**不 strip**；因此 overlap 落在空白上时块首可能以空白开头 → 见债务表）；
- `ordinal` 从 0 起连续；`doc_id` / `source` / `title` 从 `Document` 继承；
- **`text` 为空的文档返回 `[]`**，不抛异常（空文档是数据事实，不是程序错误）。

## 八、向量化层契约（`embeddings/`）

**导入方式**：`from ragkit.embeddings import embed_text`
**签名**：`embed_text(text: str, *, dim: int) -> list[float]`

### 它是干什么的

把"一段文本"变成"定长单位向量"，充当 **dense 检索通道**。没有它：混合检索只剩 BM25 一条腿，RRF 融合与第 14 阶段的消融实验都无从谈起。

### 决策与规则（第 9 轮拍板）

| 项 | 规则 |
|---|---|
| 输入 | 只吃 `str`；**不 import numpy、不认识 `Chunk`** |
| token 通道 | `tokenize(text)`（双通道、保留重复）——与 BM25 同一 token 流 |
| 映射 | 对**每个 token** 用 `sha256`：前 4 字节定下标（`% dim`）、第 5 字节奇偶定 ±1 符号 |
| 权重 | 原始词频（出现一次加一次） |
| 归一化 | L2 归一化在**本层内**完成，返回值恒为单位向量 |
| 空 token | 返回**全零向量**（不抛异常、不除零） |
| 校验 | `dim <= 0` → `ValueError` |
| 关键约束 | **索引侧与查询侧必须同函数 + 同 `dim`**；`dim` 由调用方从配置传入，本层不读配置 |

### 两个必须记住的性质

- **确定性**：只依赖 `sha256`（加密哈希，不受 `PYTHONHASHSEED` 影响）——同一文本跨进程得到同一向量（有测试锁死）；**绝不能用内置 `hash()`**。
- **字面级**：不懂语义、不懂语序。定位是"dense 通道的确定性替身"，真实收益由第 14 阶段消融数据判定。

### 一个典型错误（本轮的实战教训）

对**整段文本**做一次 `sha256` 再循环铺满 dim，会得到"任何两段文本都 ≈0.75 相似"的无用向量（sha256 雪崩 + 全非负均匀分量）。**哈希对象必须是"词"（最小语义单元），不是"文本"。**

## 九、向量库层契约（`stores/`）

**导入方式**：`from ragkit.stores import VectorStore, write, load`

### 它是干什么的

把"每块一个向量"持久化到磁盘，让"建索引"与"查询"分离。没有它：每次查询都要重跑 embedding，且增量更新无从谈起。

### 公开 API

| 接口 | 签名 |
|---|---|
| `VectorStore` | dataclass：`ids` / `matrix`(float32, N×dim) / `metadata`；属性 `dim`、`__len__` |
| `write` | `(directory, *, dim, ids, vectors, metadata) -> None` |
| `load` | `(directory) -> VectorStore` |

### 磁盘布局（四个文件，第 i 个元素对应同一块）

```
manifest.json   → {"version": 1, "dim": 512, "count": N}   ← 提交点，最后写
ids.json        → chunk_id 列表（JSON 数组）
vectors.npy     → (N, dim) float32
metadata.json   → 每个 chunk 的 metadata（JSON 数组）
```

### 写时校验（`write`，fail-fast）

`dim <= 0` / 三列表长度不等 / `ids` 重复 / 任一向量长度 ≠ dim → `ValueError`。

### 加载校验（`load`，守住不变式）

| 情况 | 行为 |
|---|---|
| manifest 缺失 / 非法 | `StoreCorruptError` |
| 数据文件**缺失** | `FileNotFoundError`（与"损坏"区分） |
| 数据文件**损坏**（读不了） | `StoreCorruptError` |
| `matrix.shape[1] != manifest["dim"]` | `StoreCorruptError` |
| `matrix.shape[0] != len(ids) != len(metadata)` | `StoreCorruptError` |

### 两条核心原则

- **三元组同序**：`ids[i]` ↔ `matrix[i]` ↔ `metadata[i]` 是同一块，读时校验行数一致；
- **原子落盘**：先写 `.tmp`，再逐文件 `os.replace`，manifest 最后写作为提交点。**单文件原子、四文件不整体原子**（见债务表 12）。

### 一个已知取舍

`ids.json` / `metadata.json` 用"整个 JSON 数组"而非 JSONL（每行一个）。更简单；代价是追加/删行要整读整写——阶段 8 反正要重写矩阵，可接受。

## 十、检索层契约（`retrieval/`）

**导入方式**：`from ragkit.retrieval import BM25Index, dense_search, rrf_fuse, weighted_fuse, rerank, search, RetrievalResult`

检索层是**两条腿 + 融合器 + 精排 + 编排**：BM25（稀疏）与 dense（向量点积）各自返回 `list[ScoredChunk]`，RRF 融合成 top_k，`rerank` 精排到 final_k，`search` 编排全程并生成 trace。BM25 分数**无上界、不归一化**、dense 分数是**余弦相似度（−1~1）**——两者量纲不可比，这正是用 RRF 的 rank 融合、而非直接加权的原因。

### 公开 API

| 接口 | 签名 |
|---|---|
| `BM25Index` | `__init__(chunks, *, k1=1.5, b=0.75)`；`search(query, *, top_k=20) -> list[ScoredChunk]` |
| `dense_search` | `(query, store, id_to_chunk, *, dim, top_k=20) -> list[ScoredChunk]` |
| `rrf_fuse` | `(results: list[list[ScoredChunk]], *, k=60, top_k=20) -> list[ScoredChunk]` |
| `weighted_fuse` | `(results, *, alpha=0.9, k=60, top_k=20) -> list[ScoredChunk]`——加权排名融合 S=α·S1+(1-α)·S2 |
| `rerank` | `(candidates, query, store, *, dim, final_k) -> list[ScoredChunk]` |
| `search` | `(query, *, bm25, store, id_to_chunk, dim, retrieval) -> RetrievalResult` |

### 核心规则

| 项 | 规则 |
|---|---|
| 建索引 | `__init__` 统计 `df`（词→含该词的块数）、每块词频（`Counter`）、块长（token 数）、`N`、`avgdl` |
| 打分 | `search` 只用这些统计，**不重新分词任何块**；只对 query 里**语料中出现过**的词打分（`df=0` 的词不参与，否则 idf 会爆） |
| 规范化 | `search` 内部 `tokenize(query)`（tokenize 已含 normalize）——chunk.text 已被 chunking 层规范化，query 无人保证，故由 search 负责 |
| token 通道 | `tokenize()` 双通道，与 dense 同一 token 流 |
| 分数 | 无上界、不归一化；`stage="bm25"` |
| 空输入 | 空 query → `top_k` 个分数全 0 的块（与 dense 对齐）；空语料 / query 词全不在语料 → `[]` |

### 公式（契约）

```
score(D, Q) = Σ_{t∈Q} IDF(t) · f(t,D)·(k1+1) / ( f(t,D) + k1·(1 − b + b·|D|/avgdl) )
IDF(t) = ln(1 + (N − df(t) + 0.5) / (df(t) + 0.5))
```

### 已知边界

BM25 目前**内存驻留、不持久化**：进程重启后 `__init__` 要重新统计（见债务表 13）。增量删除（墓碑）属阶段 8。

### dense 检索契约（`dense_search`）

| 项 | 规则 |
|---|---|
| 打分 | `embed_text(query, dim=dim)` → `store.matrix @ q` → 点积即**余弦相似度**（两侧向量都已 L2 归一化） |
| 排序 | `scores.argsort()[::-1][:top_k]`；返回 `stage="dense"`、`score` 为纯 Python `float` |
| 空 query | `embed_text` 给全零向量 → 点积全 0 → 返回 `top_k` 个分数全 0 的块（与 BM25 对齐） |
| 空 store | `matrix` 为 (0, dim) → 返回 `[]` |
| 归一化责任 | **在 embeddings 层**（写向量时保证单位向量）；store 原样存、dense 只点积。换真模型未归一化会退化成内积、长块虚高 |
| 前提 | `store.ids` 里每个 id 都必须能在 `id_to_chunk` 查到；`dim` 与向量列数一致 |

### 融合契约（`rrf_fuse` / `weighted_fuse`）

| 项 | 规则 |
|---|---|
| 公式 | RRF：每块分数 = Σ_腿 1/(k + rank)，`k=60` |
| 加权公式 | `weighted_fuse`：S(d) = α·S1(d) + (1-α)·S2(d)，S_i 为第 i 腿的 RRF 排名分；第一腿（BM25）权重 α、第二腿（dense）权重 1-α；α=0.5 与等权 RRF 等价（差常数因子） |
| 聚合 | **按 `chunk_id` 聚合**：同一块跨腿只留一份、rank 分累加（不是 concat 后重复出现） |
| 输出 | `stage="rrf"`，按融合分降序，`top_k` 截断 |
| 单腿退化 | 只传一条腿 `[leg]` 时退化为该腿的 rank 顺序（α 不参与，权重归一化为 1） |
| 空腿容错 | 某条腿为空列表 `[]` 时跳过，不影响其他腿；全部空返回 `[]` |
| 接口形状 | `list[list[ScoredChunk]]` 是刻意选的：把"腿的数量"从签名写死变成运行时可变，消融（1 腿）/ 未来加腿都不用改签名 |

### 重排契约（`rerank`）

| 项 | 规则 |
|---|---|
| 分数 | dense 余弦：`store` 里候选向量 · `embed_text(query)` 点积，连续、有界（−1~1） |
| 输出 | `stage="rerank"`、`score` 纯 `float`、降序截断到 `final_k` |
| sub_scores | `prev` 记录精排前的分数；原有 `sub_scores` 保留（`{**c.sub_scores, "prev": c.score}`） |
| 不在库候选 | `chunk_id` 不在 `store.ids` 里的候选无法打分，被丢弃 |
| 空候选 | 返回 `[]` |

### 流水线契约（`search`）

| 项 | 规则 |
|---|---|
| 编排 | 按 `retrieval.sparse_enabled / dense_enabled` 跑腿 → 按 `retrieval.fusion` 选 `rrf_fuse`（等权）或 `weighted_fuse`（加权 α=`fusion_alpha`）融合 top_k → `rerank_enabled` 时 `rerank` 到 final_k |
| 关重排 | `rerank_enabled=False`（**默认**）时融合后直接 `[:final_k]`，`stage` 保持 `"rrf"` |
| 两腿都关 | 返回 `RetrievalResult(results=[], trace=RetrievalTrace())`，不报错 |
| trace | 每阶段 `perf_counter()` 计时；`candidate_count` 口径：`bm25`/`dense` 记腿返回数、`fusion` 记融合后数、`rerank` 记 `final_k` |
| 返回 | `RetrievalResult`（`results` + `trace`），查询编排的对外入口；建索引（load → chunk → embed → store → BM25Index）属阶段 8 |

## 十一、建库层契约（`index/`）

**导入方式**：`from ragkit.index import build, load_index, BuiltIndex, write_chunks, read_chunks`

### 它是干什么的

把"一堆零件"组装成"一条产线"：输入文档目录，输出**可查询索引**（落盘 + 内存就绪资源）。没有它：`search` 的四个入参要每个调用方手工拼装，且 `id_to_chunk` 根本不落盘——进程一重启就没了；增量更新也无从谈起。

### 公开 API

| 接口 | 签名 |
|---|---|
| `build` | `(root: Path, cfg: AppConfig) -> BuiltIndex` |
| `load_index` | `(index_dir: Path) -> BuiltIndex` |
| `BuiltIndex` | dataclass：`bm25` / `store` / `id_to_chunk` / `dim` / `failures` |
| `write_chunks` | `(path: Path, chunks: list[Chunk]) -> None` |
| `read_chunks` | `(path: Path) -> list[Chunk]` |

### 核心规则

| 项 | 规则 |
|---|---|
| 编排 | `load_dir` → `chunk_document`（`cfg.chunking` 参数）→ `embed_text`（`cfg.embedding.dim`）→ `stores.write`（**先调它建目录**）→ `write_chunks` → `BM25Index`（用本次结果直接建，不重读盘） |
| 空语料 | 合法产物：空 store + 空 chunks.jsonl + 空 BM25Index，不报错 |
| 坏文件 | 进 `BuiltIndex.failures`（`LoadReport.failures` 原样搬运），不炸整批 |
| `load_index` | `stores.load` → `read_chunks` → **硬不变式** `set(chunks 的 chunk_id) == set(store.ids)`，不一致 `ValueError`（消息带两侧数量——正是拦截"write 与 write_chunks 之间的半成品索引"） |
| BM25 恢复 | **从落盘 chunks 重建统计**（第 14 轮决策 2）：统计是可再生数据，重建优于新增落盘格式——债务 13 就此消化 |
| `dim` | build 时来自 `cfg.embedding.dim`；load 时来自 `store.dim`（`load_index` 不带 cfg，避免过度设计） |

### chunks.jsonl 格式（第 14 轮拍板，改动即破坏性变更）

- **JSONL**：每行一个 `Chunk.to_dict()`，UTF-8；与 stores 的"整个 JSON 数组"取舍相反——chunks 面向**增量追加**（坏一行只损一块），stores 当时的判断是"阶段 8 反正要重写矩阵"；
- 写入走 `tmp + os.replace`（与 stores 同款单文件原子策略）；
- 读取：空行跳过；坏行 `ValueError` 带**路径与行号**；文件缺失 `FileNotFoundError`（与 stores"缺失按缺失、损坏按损坏"口径一致）。

## 十二、生成层契约（`generation/`）

**导入方式**：`from ragkit.generation import answer_question`

### 它是干什么的

把"检索到的证据"翻译成"对用户的回答"——`RetrievalResult + question` 进，`Answer` 出。它是 `RetrievalResult` 的**第一个生产消费者**（此前只有测试消费它）。

### 公开 API

| 接口 | 签名 |
|---|---|
| `answer_question` | `(question: str, result: RetrievalResult, *, llm: LLMConfig) -> Answer` |

### 组装规则（第 15 轮拍板）

| 情形 | 行为 |
|---|---|
| `results` 为空（拒答） | `refused=True`、`answer=""`、`citations=[]`、`contexts=[]`、`confidence=0.0` |
| 非空（正常） | `refused=False`；`answer = results[0].chunk.text`（**抽取式**，决策 1）；`contexts = [每块 text]`；`citations` 逐条 `Citation(index=i+1, source, snippet, title)`，编号从 1 起、顺序同 results；`confidence = results[0].score`（**rerank 余弦搬运**，决策 2，不是新评分系统） |
| 两种情形 | `question` 原样进 `Answer.question`；**`trace = result.trace` 原样挂载（拒答也挂）**——约定"`trace=None` 表示**没有**检索轨迹"，拒答时检索确实发生了，挂上才是遵守本义 |
| `provider="openai_compatible"` | **fail-fast：`NotImplementedError`**——配置是人的意图，静默降级成抽取式是谎报能力 |

### 两个必须记住的辨析（第 15 轮架构问题纠正）

- **contexts 给机器、citations 给人**：`contexts` 是喂给将来 LLM 的纯文本材料；`citations` 是给人溯源的结构化引用（编号/来源/片段/标题）。两者值相同是**抽取式的巧合**——接真 LLM 后 `answer` 变成生成文本，`contexts`/`citations` 各自保持职责，立刻分开。字段语义由**消费者**定义，不由当前值是否相同决定。
- **传整个 `LLMConfig` 而非 `provider: str`**：将来接 LLM 需要 `model`/`api_key`/`base_url`（全在配置对象里）；配置对象加字段不破坏签名（第 1 轮验证过），散参数加一个就是破坏性变更——所有调用点重写。

## 十三、HTTP API 契约（`api/`）

**导入方式**：`from ragkit.api import create_server, make_handler`

**启动方式**：`ragkit serve [--host 127.0.0.1] [--port 8000]`——启动时 `load_config` → `load_index`（**索引常驻内存，只付一次冷启动**；变更需重启，热更新为扩展），`Ctrl+C` 退出码 0；索引缺失 → 提示先 build、退出码 1。

### 端点（第 17 轮拍板）

| 端点 | 行为 |
|---|---|
| `POST /ask` `{"query": str}` | 200 + `Answer.to_dict()` JSON——**拒答也是 200**，用 `refused: true` 表达（与 CLI 拒答=退出码 0 同语义：拒答是业务正常结果，不是资源不存在） |
| `GET /healthz` | 200 + `{"version", "chunks", "status": "ok"}`（运维/评测前置检查） |
| 错误翻译表 | 400 = 请求体问题（非 JSON / 缺 query / query 非非空 str，消息给具体原因）；404 = 路径不存在；405 = 方法不对；500 = 未知异常，**对外只给 `{"error": "internal"}` 不泄堆栈**（读者分层：开发者查日志，堆栈不进响应体） |

### 壳芯分离（契约）

- **芯**：`_answer_payload(query, built, cfg) -> dict` 纯函数（search → answer_question → `to_dict()`），不碰 socket，可直调单元测试；
- **壳**：handler 只做 HTTP 细节（解析 body、翻译状态码、写日志）——"CLI 三件事"在 API 的四件事版本：解析、调芯、翻译、日志；
- **格式化零进领域层**：CLI 的 print 与 API 的 JSON 共享 `Answer` 结构化契约，不是格式化函数（第 16 轮问题 3 的落地）。

### 日志（logging 标准库）

- 库只 `getLogger("ragkit.api")`、**应用侧（cli.py 的 serve）才 basicConfig**——格式归调用方定，库不越界；
- 每请求一行：`POST /ask | 200 | 12.3ms | body_len=N`（INFO，stderr）；启动一行（版本、地址、索引块数）。

## 十四、评测层契约（`evaluation/`）

**导入方式**：`from ragkit.evaluation import recall_at_k, mrr, load_qrels, evaluate`

### 它是干什么的

给“检索质量好不好”装上量尺——评测集（query+标注）进，指标（recall@k / MRR / 耗时表）出。没有它：阶段 14 消融实验拿什么数据证明关一条腿会退化多少、交付报告拿什么数字展示质量。

### 指标契约（纯函数，手算可验）

| 接口 | 定义 |
|---|---|
| `recall_at_k(retrieved, relevant, k)` | 前 k 个 doc_id 里命中的相关数 / 相关总数；`relevant` 空 → 0.0（不除零）；`k<=0` → `ValueError`（**参数校验最先**，即使 relevant 也空） |
| `mrr(retrieved, relevant)` | 第一个相关文档所在位置 rank 的倒数；无命中 / `relevant` 空 → 0.0 |

`retrieved` 是**已去重、按排名排列的 doc_id 序列**（指标函数只认有序序列，不认 `ScoredChunk`——最小依赖、可直测、可复用）。`relevant` 用 `set`/`frozenset`：**相关是无序的成员关系**（0/1 相关，不分等级；分级属 nDCG 扩展）。

### 评测集契约（`data/eval/qrels.json`，第 18 轮拍板）

- 格式：`[{"query": str, "relevant": [doc_id, ...]}, ...]`；`load_qrels` 校验（顶层列表、query 非空、relevant 非空列表），`relevant` 去重为 `frozenset`；
- **评测单元 = 文档**（`doc_id` = 相对 POSIX 路径，第 7 轮定）：`chunk_id` 是派生量，随 chunk_size 失效，标注它无意义；
- 当前 300 条 query（**全部手写自然语言，0 重复**），对应 `data/raw` 的 100 篇文档（20 正 + 80 **误导**）。语料由 `scripts/generate_corpus.py` 生成；**query 由 `scripts/queries_data*.py` 手写**，每主题 15 条、措辞多样、带场景，刻意避免与文档标题/概念词逐字重叠。旧版"概念词 × 问句模板"的合成 query 与文档词汇高度重叠、指标虚高，已废弃。

### 评测编排（`evaluate`）

`evaluate(built, cfg, qrels, ks=(1,2,...,10)) -> EvalReport`：逐条 `search` → **doc_id 去重**（一个文档多块只算一次，防虚高）→ 算 recall@k/mrr → 汇总平均 + 耗时表（`LatencyStats`：`cold_ms` 进程内首查 + `warm_p50/p95/mean`）。

**耗时口径澄清（本轮实测发现）**：`evaluate` 的“冷启动”是**进程内首查**，**不含 jieba**——因为 `built` 在 build/load_index 时已经加载了 jieba。真正的 jieba 冷启动（~1.8s + BM25 重建分词）发生在 build/load_index 层，不属检索耗时。检索各阶段的热耗时看 `RetrievalTrace`（第 13 轮起就有），本轮把它们汇总成 P50/P95/均值。

**实测基线（2026-10-17，300 条手写 query）：`recall@1=0.833`、`recall@3=0.973`、`MRR=0.899`**——手写自然语言 query 后检索任务更公平（此前模板合成 query 词汇重叠、指标失真）。

### 消融实验（`run_ablation`，第 19 轮）

4 组单变量对照（单腿组同时关 rerank，隔离变量）：

| 组 | recall@1 | MRR | 边际贡献（baseline − 关掉它） |
|---|---|---|---|
| baseline（全开） | 0.833 | 0.899 | — |
| **bm25_only** | **0.910** | **0.950** | BM25 腿 +0.000 |
| dense_only | 0.833 | 0.899 | **dense 腿 −0.08** |
| **no_rerank** | **0.910** | **0.948** | **rerank −0.08** |

**结论（手写自然语言 query 下）**：dense 腿与 rerank 都是**负资产（各 −0.08）**，纯 BM25 与 no_rerank 打平最优（recall@1=0.910）。`baseline == dense_only`（0.833）再次印证 rerank 用 dense 余弦一票否决、把 baseline 退化成 dense 主导。

**关键发现：query 质量影响消融结论**。模板合成 query（词汇与文档高度重叠）会**高估 dense 腿**（短文档时 −0.02，几乎无害）；手写自然语言 query 措辞多样、dense 的字面级哈希重叠变弱，dense 的负贡献回升到 −0.08，而 BM25 的词项匹配（罕见词 idf）持续稳定。这提示：**合成 query 测不出真实检索能力，评测集必须用接近真实提问的自然语言**。

**落点**：上线配置默认**关 rerank**（用 RRF 融合直接取 final_k）；dense 腿保留（长文档下几乎无负贡献，且融合略优于纯 BM25）。rerank 标为“换真 embedding（cross-encoder）后再评估”的扩展。

## 十五、测试覆盖

| 测试文件 | 覆盖内容 | 条数 |
|---|---|---|
| `tests/test_smoke.py` | 包可导入、`__version__` 格式、`--version` 输出与退出码、无参数与 `--help` 行为 | 3 |
| `tests/test_schemas.py` | 各模型往返、键集合契约、JSON 可序列化、默认值不共享、必填字段缺失拒绝（参数化）、新增字段兼容、未知键忽略 | 36 |
| `tests/test_config.py` | 默认值、文件不存在、YAML 覆盖、空文件、顶层非映射、非法取值（6 条参数化）、未知键、往返、环境变量覆盖与深合并、类型转换、顶层字段、非法/未知环境变量、无关变量忽略、快照脱敏、JSON 可序列化、repr 不泄漏 | 25 |
| `tests/test_text_normalize.py` | 换行统一、NFKC（全角 ASCII / 中文标点）、零宽与控制字符删除、行尾空白与制表符、空行折叠、标点与换行保留、幂等性、空输入 | 9 |
| `tests/test_text_tokenize.py` | 中文词、相邻 bigram、ASCII 不产 bigram、纯标点过滤、URL/版本号/数字保留、中英数混排、双通道合并、全角半角等价、空输入 | 9 |
| `tests/test_loaders.py` | 必填 metadata 键集合、坏文件隔离、GBK 回退与编码记录、BOM 剥离、标题提取与回退、排序、跳过隐藏路径、相对 POSIX 路径、cwd 无关、缺失 root 报错 | 15 |
| `tests/test_chunking_fixed.py` | 参数校验、边界选择（11 条参数化：优先级与位置、下限拒绝、不读窗口外）、重叠与末块、大 overlap 前进、偏移保留原文、小输入穷举不变式 | 28 |
| `tests/test_chunking_document.py` | 规范化偏移不变式、metadata 四键、content_hash 口径、重复块序号计数、空文本、参数校验 | 8 |
| `tests/test_chunking_ids.py` | ID 格式、序号下限校验、稳定性、**局部性**、变化粒度、跨文档隔离、唯一性 | 8 |
| `tests/test_embeddings_hashing.py` | 长度恒为 dim、单位向量、确定性、**跨进程稳定**（subprocess + PYTHONHASHSEED）、相似度按 token 重叠排序、空 token、dim 校验 | 14 |
| `tests/test_vector_store.py` | 三元组同序往返、shape/dtype、长度/重复 id/dim 校验、空库、缺失目录、损坏文件、manifest dim 不匹配、无 tmp 残留、中文往返、可复现 | 14 |
| `tests/test_bm25.py` | 手算样例（分数精确对齐）、词频/罕见词/长度三直觉、k1/b 参数化、空 query（全 0 分块）/语料、未知词、stage 与 top_k、query 规范化、确定性 | 11 |
| `tests/test_dense.py` | 点积降序、score 为纯 float、stage、top_k、同文本余弦=1、空 query 全 0 分块、空 store、确定性 | 9 |
| `tests/test_fusion.py` | 跨腿聚合累加、去重、保留 Chunk 对象、单腿退化、空腿容错、全空、top_k、k 常数、加权融合 α 权重/极端值/单腿退化/stage | 12 |
| `tests/test_rerank.py` | 手算样例、final_k 截断、stage、sub_scores.prev、空候选、不在库候选丢弃、确定性 | 8 |
| `tests/test_pipeline.py` | 开关组合（只稀疏/只稠密/都关/关重排）、默认关 rerank、trace 阶段顺序与候选数口径、总耗时=各阶段和、返回类型 | 9 |
| `tests/test_index_build.py` | 五文件产物、id 三方一致、坏文件隔离、空目录、可直接检索、可复现 | 7 |
| `tests/test_index_load.py` | 与 build 结果等价（分数一致）、缺文件 / id 不一致 / 坏行拦截、dim 与 failures 口径 | 5 |
| `tests/test_generation.py` | 正常组装、引用编号与顺序、拒答（trace 仍挂）、fail-fast、序列化、端到端链路 | 6 |
| `tests/test_cli.py` | build 统计与坏文件、ask 回答与引用、serve/eval 无索引、eval 跑通落盘、拒答=0、配置/语料错误=1、环境隔离、jieba 降噪 | 11 |
| `tests/test_api.py` | 真服务器集成：/ask 回答 JSON、拒答=200+refused、400（坏 JSON/缺 query，参数化）、404/405、/healthz、请求日志 | 12 |
| `tests/test_metrics.py` | recall 手算、k 越界、空 relevant/retrieved、k<=0 抛、mrr 手算/无命中/空 relevant | 8 |
| `tests/test_evaluation.py` | doc_id 去重保持首现顺序、端到端跑评测集、空 qrels 返回全 0 | 3 |
| `tests/test_ablation.py` | 对照组开关契约（4 组单变量）、run_ablation 跑通与指标范围 | 2 |
| **合计** | | **272** |

**当前结果**：**272 passed**（2026-10-17）
**历史自证**：先在真实环境里设 `RAG__RETRIEVAL__TOP_K=99`，再跑 `pytest -q` → 结果不变（2026-10-07 于 64 条时验证，可随时重跑）

## 十六、阶段状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| 0 | 项目骨架、可安装、可测试 | ✅ 完成 |
| 1 | 领域模型（7 个模型） | ✅ 完成 |
| 1 | 配置系统（模型 + YAML + 校验 + 环境变量覆盖 + 脱敏） | ✅ 完成（2026-10-07，64 passed） |
| 2 | 文本清洗 + 分词（`text/`） | ✅ 完成（2026-10-09，82 passed） |
| 2 | 文件加载（`loaders/`，坏文件不炸整批） | ✅ 完成（2026-10-11 实测：GBK 回退 / 标题提取 / 坏文件隔离 / 相对路径坐标系全通过） |
| 3 | 分块 + 稳定 `chunk_id`（`chunking/`） | ✅ 完成（2026-10-11，141 passed） |
| 2（余） | HTML / PDF 加载器 | ⏸ 有意识推迟（见债务表） |
| 4 | 向量化（`embeddings/`，Hashing Embedding） | ✅ 完成（2026-10-13，155 passed） |
| 5 | NumPy 向量库与持久化（`stores/`） | ✅ 完成（2026-10-13，169 passed） |
| 6 | BM25（`retrieval/`） | ✅ 完成（2026-10-14，180 passed） |
| 7 | 混合检索 + RRF 融合 + 重排 + trace（`retrieval/`） | ✅ 完成（第 13 轮，213 passed）：dense / RRF / rerank / trace / pipeline 全就位 |
| 8 | 建库流水线与索引管理 | 部分完成：全量 `build` + `load_index`（第 14 轮）；**增量更新为扩展**（触发信号：全量重建实测慢到痛） |
| 9 | 生成层（`generation/`） | ✅ 完成（第 15 轮，231 passed）：`RetrievalResult` 的第一个生产消费者就位；`openai_compatible` 为扩展（触发信号：拿到密钥 + 网络可用） |
| 10 | CLI（`ragkit build` / `ragkit ask`） | ✅ 完成（第 16 轮，239 passed）：全链路暴露成命令；`--json` / REPL 为扩展 |
| 11 | HTTP API + 请求日志 | ✅ 完成（第 17 轮，252 passed）：`POST /ask` / `GET /healthz`，索引常驻；FastAPI 迁移 / 鉴权为扩展 |
| 12 | 评测集与指标（`evaluation/`） | ✅ 完成（第 18~19 轮，267 passed）：recall@k(1~10) / MRR / 耗时表；100 篇语料 + 300 条手写 query |
| 13 | 消融实验（`evaluation/ablation.py`） | ✅ 完成（第 19 轮）：4 组对照——手写 query 下 dense 腿 −0.08、rerank −0.08 负贡献，纯 BM25 最优（recall@1=0.910） |
| 14 | 交付：README 收尾 + 打包 | ✅ 完成（第 21 轮）：README 重写（四命令/架构/评测结论）、版本升 1.0.0、pyproject 加 readme 字段 |
| 15 | 总结报告 | ✅ 完成（第 22 轮）：`SUMMARY.md` 沉淀全项目——架构全景、消融结论、设计决策、踩坑规律、演进方向 |

## 十七、目录创建进度

按"需要它的那一阶段"创建，不提前建空目录：

| 目录 | 状态 |
|---|---|
| `configs/` | ✅ 已建（第 4 轮） |
| `src/ragkit/text/` | ✅ 已建（第 6 轮） |
| `src/ragkit/loaders/` | ✅ 已建（第 7 轮） |
| `src/ragkit/chunking/` | ✅ 已建（第 8 轮） |
| `data/raw/` | ⬜ 做真实数据实验时建（尚未创建） |
| `src/ragkit/embeddings/` | ✅ 已建（第 9 轮） |
| `src/ragkit/stores/` | ✅ 已建（第 10 轮） |
| `data/index/` | ⬜ 真实语料建库时由 `build` 自动创建（测试用 tmp_path 覆盖 index_dir） |
| `src/ragkit/retrieval/` | ✅ 已建（第 11 轮） |
| `src/ragkit/index/` | ✅ 已建（第 14 轮） |
| `src/ragkit/generation/` | ✅ 已建（第 15 轮） |
| `src/ragkit/api/` | ✅ 已建（第 17 轮） |
| `src/ragkit/evaluation/` | ✅ 已建（第 18 轮） |
| `data/raw/`、`data/eval/` | ✅ 已建（第 18 轮：10 篇语料 + 12 条评测集） |
| `data/eval/`、`reports/` | ✅ 已建（第 18 轮：评测集 + 报告落盘） |
| `scripts/` | ✅ 已建（第 19 轮：`generate_corpus.py` 程序化生成语料与评测集） |

## 十八、常用命令

```powershell
cd "C:\Users\王佳浩\Desktop\项目"

# 安装（含开发依赖）
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 全部测试
.\.venv\Scripts\python.exe -m pytest -q

# 单文件 / 单条测试
.\.venv\Scripts\python.exe -m pytest tests/test_config.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_schemas.py::test_document_roundtrip -q

# 每个测试文件的用例数
.\.venv\Scripts\python.exe -m pytest --collect-only -q

# 测试隔离自证：先在真实环境里下毒，结果必须不变
$env:RAG__RETRIEVAL__TOP_K = "99"
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:RAG__RETRIEVAL__TOP_K

# 文本层快检
.\.venv\Scripts\python.exe -c "from ragkit.text import tokenize, normalize_text; print(normalize_text('ＡＢＣ　１２３\r\n\r\n\r\n中')); print(tokenize('容器 cold 启动 v1.2.3'))"

# 加载层快检：临时目录里放 UTF-8 标题 md + GBK txt + 二进制坏文件
.\.venv\Scripts\python.exe -c "from pathlib import Path; import tempfile; d=Path(tempfile.mkdtemp()); (d/'sub').mkdir(); (d/'sub'/'a.md').write_text('# \u6807\u9898\n\n\u6b63\u6587', encoding='utf-8'); (d/'b.txt').write_bytes('\u51b7\u542f\u52a8'.encode('gbk')); (d/'bad.md').write_bytes(b'\xff\xfe\x00\x01'); from ragkit.loaders import load_dir; r=load_dir(d); [print('doc:', x.source, '| title:', x.title, '| enc:', x.metadata['encoding'], '| path:', x.metadata['path']) for x in r.documents]; [print('failure:', f.path, '|', f.error_type) for f in r.failures]"

# 分块层快检：手算样例会给出 [(0, 10), (8, 18)]
.\.venv\Scripts\python.exe -c "from ragkit.chunking import iter_spans; print(iter_spans('AAA\n\nBBB\n\nCCC\n\nDDD', chunk_size=10, overlap=2))"

# 向量层快检：共享词 → 余弦 1.0，无关 → 0.0
.\.venv\Scripts\python.exe -c "from ragkit.embeddings import embed_text; a=embed_text('\u5bb9\u5668\u51b7\u542f\u52a8', dim=512); cos=lambda x,y: sum(i*j for i,j in zip(x,y)); print(round(cos(a, embed_text('\u5bb9\u5668\u51b7\u542f\u52a8\u3002', dim=512)),3), round(cos(a, embed_text('\u6570\u636e\u5e93\u8fde\u63a5\u6c60', dim=512)),3))"

# 向量库快检：写 → 读，打印 shape / dim / len
.\.venv\Scripts\python.exe -c "from pathlib import Path; import tempfile; from ragkit.stores import write, load; d=Path(tempfile.mkdtemp()); write(d, dim=4, ids=['a','b'], vectors=[[1,0,0,0],[0,1,0,0]], metadata=[{'k':'x'},{'k':'y'}]); s=load(d); print('shape:', s.matrix.shape, '| dim:', s.dim, '| len:', len(s))"

# 命令行入口
.\.venv\Scripts\ragkit.exe --help
.\.venv\Scripts\ragkit.exe --version

# CLI 建库（第 16 轮）：语料目录默认 cfg.data_dir，--root 可覆盖
.\.venv\Scripts\ragkit.exe build

# CLI 问答：打印回答 + 编号引用来源
.\.venv\Scripts\ragkit.exe ask "容器冷启动怎么优化？"

# 评测（第 18 轮）：跑评测集，打印摘要 + 落盘 reports/eval.json
.\.venv\Scripts\ragkit.exe eval

# API 服务（第 17 轮）：索引常驻，Ctrl+C 停止
.\.venv\Scripts\ragkit.exe serve --port 8000
# 另开终端测试：
#   curl -X POST http://127.0.0.1:8000/ask -d "{\"query\": \"容器冷启动\"}"
#   curl http://127.0.0.1:8000/healthz

# CLI 退出码约定（第 16 轮拍板）：0 = 成功（含拒答，拒答是业务正常结果）；
# 1 = 运行错误（配置非法 / 索引缺失或损坏 / 语料目录不存在）；2 = 用法错误（argparse 自带）
# CLI 是薄壳：只做解析参数、调领域函数、格式化输出；领域层延迟 import，--version 秒回

# 脱敏自检（两个都必须是 False）
.\.venv\Scripts\python.exe -c "import json; from ragkit.config import AppConfig; c = AppConfig(llm={'api_key': 'sk-SECRET'}); print('snapshot 泄漏:', 'SECRET' in json.dumps(c.snapshot()), '| repr 泄漏:', 'SECRET' in repr(c))"

# 改名后确认旧名已彻底清除（必须 0 命中）
Select-String -Path (Get-ChildItem -Recurse -Include *.py -Path src,tests).FullName -Pattern "旧名字"
```

## 十九、已知技术债

| # | 内容 | 影响 | 计划 / 触发信号 |
|---|---|---|---|
| 1 | **尾块过短**：实测 `chunk_size=10, overlap=2` 切 19 字符文本 → 末块 7 字符（overlap 2 + 新内容 5） | 短块在 BM25 里因长度归一化虚高得分，可能挤占 `top_k` | 第 9 阶段实测 `avgdl` 与引用质量；确有影响再加**显式的尾块合并策略**（可开关、可消融） |
| 2 | **块首可能以空白开头**（overlap 落在 `\n\n` 上） | 引用片段开头出现空行，观感差 | 不能 strip（会破坏 `chunk.text == 规范化切片` 不变式）→ 第 9 阶段看实际观感再定 |
| 3 | HTML / PDF 加载器缺失 | 这两类来源暂时进不来 | 真实数据里出现、且确属关键来源时再补 |
| 4 | 尚无静态检查（ruff / mypy） | `ids.py` 函数内 import、`chunking/__init__.py` 借道导入、行尾空格这类问题只能靠人工 | 第 15 阶段进 CI；也可提前加 ruff |
| 5 | `.gitignore` 缺少 `!.env.example` 例外 | 将来 `.env.example` 无法提交 | 建立该文件时 |
| 6 | 仓库提交滞后 | 已有 4 次提交（最后 `586d549` / 2026-10-09），当前 **14 个条目未提交**（loaders/、chunking/、9 个测试文件与文档） | 本轮结束提交一次，之后每轮一次 |
| 7 | `configs/default.yaml` 与模型默认值靠人工保持一致 | 改默认值时可能漏改 YAML | 可写成测试（`load_config(...) == AppConfig()`） |
| 8 | `tokenize()` 内部重复规范化 | 同一输入被 `normalize_text` 处理 3 次（自身 + 两个子函数各一次）；幂等故无功能影响 | 数据量大时改为内部函数接收已规范化文本 |
| 9 | ~~jieba 向 stderr 打印自述噪声~~ **已消化（第 16 轮决策 3）**：`text/tokenize` 模块加载时 `jieba.setLogLevel(WARNING)`，源头一次治理所有入口（实测子进程 stderr 完全干净） | —— | **剩余（第 18 轮部分落实）**：检索各阶段热耗时已由 `evaluate` 汇总成 P50/P95；jieba ~1.8s 冷启动归 build/load_index 层，不混入检索耗时统计 |
| 10 | 根目录残留 `.test-tmp-loaders-20261009-a` / `-b` | 未进 `.gitignore`，会出现在 `git status` 里 | 确认无用后删除，或加进 `.gitignore` |
| 11 | 全量测试从 6.4s 涨到 17s（embeddings 测试触发 jieba 首次加载 + 两个子进程） | 测试反馈变慢，暂可接受 | 阶段 6 之后考虑 session 级 jieba 预热 fixture |
| 12 | 向量库"多文件原子性"是近似实现：逐文件 `os.replace` + manifest 最后写，**单文件原子、多文件不整体原子**；第 14 轮起扩为**五文件**（+chunks.jsonl），半成品索引由 `load_index` 的 id 一致性校验拦截 | 极端崩溃时可能留下新旧混合状态 | 触发信号：建库中途崩溃实际发生过 → 改"临时目录整体替换" |
| 13 | ~~BM25 统计内存驻留、未持久化~~ **已消化（第 14 轮决策 2）**：`load_index` 从 chunks.jsonl 重建 `BM25Index`，统计是可再生数据、不新增落盘格式。代价：重启后 `load_index` 要重新分词 | 大语料下重启变慢 | 触发信号：实测重建耗时不可接受时再考虑统计落盘 |
