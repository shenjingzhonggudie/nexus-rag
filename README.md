# RAGKit

从零手搓的中文 RAG（检索增强生成）系统，覆盖 **加载 → 分块 → 向量化 → 建库 → 混合检索 → 重排 → 生成 → 评测 → 消融** 全链路。核心算法（BM25、RRF 融合、重排、拒答、评测指标）全部自己实现。

**设计前提**：不使用 LangChain、LlamaIndex 等 RAG 框架；默认模式**离线可运行、不需要 API Key、不联网**。真实向量模型与 LLM 只作为可选适配器接入（当前为 hashing 字面级 embedding + 抽取式回答）。

## 当前状态

**全链路已贯通，四入口可用，评测与消融有量化结论。** 268 条测试全绿。

- 四个 CLI 子命令：`build` / `ask` / `serve` / `eval`；
- HTTP API：`POST /ask`、`GET /healthz`（索引常驻内存，只付一次冷启动）；
- 两套评测语料：`data/`（后端分布式，100 篇 + 300 条 query）、`data2/`（机器学习，100 篇 + 300 条 query）；
- 消融结论（详见「评测与消融」）：**当前 hashing 实现下，纯 BM25 最优，rerank 默认关闭**。

| 项 | 值 |
|---|---|
| 版本 | 1.0.0 |
| Python | >= 3.11（开发环境使用 3.12） |
| 运行平台 | 主要面向 Windows + PowerShell，代码本身跨平台 |
| 运行时依赖 | `pyyaml` `pydantic` `jieba` `numpy` |

## 快速开始

```powershell
# 1. 进入项目目录
cd "C:\Users\王佳浩\Desktop\项目"

# 2. 创建虚拟环境（用 3.12；不要用 3.14，部分依赖可能缺少预编译包）
py -3.12 -m venv .venv

# 3. 可编辑安装（-e 表示不复制代码，只写路径映射；.[dev] 一并装 pytest）
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 4. 建库（索引 data/raw → data/index）
.\.venv\Scripts\ragkit.exe build

# 5. 问答（回答 + 编号引用来源）
.\.venv\Scripts\ragkit.exe ask "容器冷启动怎么优化？"

# 6. 评测（打印摘要 + 落盘 reports/eval.json）
.\.venv\Scripts\ragkit.exe eval
```

> 为什么不先激活虚拟环境？PowerShell 的默认执行策略可能禁止运行 `Activate.ps1`，直接调用 `.\.venv\Scripts\python.exe` 效果相同，且不必改动系统设置。

### 启动 HTTP API

```powershell
.\.venv\Scripts\ragkit.exe serve --port 8000
# 另开终端：
# curl -X POST http://127.0.0.1:8000/ask -d '{"query": "容器冷启动"}'
# curl http://127.0.0.1:8000/healthz
```

### 验收命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # 预期：268 passed
.\.venv\Scripts\ragkit.exe --help                # 预期：列出 build/ask/serve/eval 四子命令
.\.venv\Scripts\ragkit.exe --version             # 预期：ragkit 1.0.0
```

## 四个命令详解

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `ragkit build` | 建库：`data/raw` → `data/index`，打印统计 | `--config PATH`（YAML 配置）、`--root PATH`（覆盖语料目录） |
| `ragkit ask QUERY` | 问答：回答原文 + `[1] 来源` 引用；拒答提示"未找到相关内容" | `--config PATH` |
| `ragkit serve` | 启动 HTTP API（`POST /ask`、`GET /healthz`） | `--host`、`--port`、`--config` |
| `ragkit eval` | 跑评测集：打印 recall@1~10 / MRR / 耗时，落盘 `reports/eval.json` | `--config`、`--qrels`、`--out` |

**退出码约定**：`0` = 成功（**含拒答**——拒答是业务正常结果，不是错误）；`1` = 运行错误（配置非法 / 索引缺失损坏 / 语料目录不存在）；`2` = 用法错误（argparse 自带）。

**配置优先级**：命令行参数 > 环境变量（`RAG__*` 前缀）> YAML 配置 > 模型默认值。默认 `data_dir = data/raw`、`index_dir = data/index`。

## 架构分层

```
loaders/      文本加载：.txt/.md/.markdown，UTF-8 + GBK 回退，坏文件隔离
chunking/     分块：固定大小 + overlap，稳定 chunk_id（内容哈希）
embeddings/   hashing 字面级 embedding（L2 归一化，离线可用）
stores/       NumPy 向量库：五文件落盘（manifest 最后写）+ 加载校验
retrieval/    BM25（idf 词权重）→ dense（向量点积）→ RRF 融合 → rerank（精排）
index/        建库编排 build / load_index（chunks.jsonl 落盘 + id 一致性校验）
generation/   answer_question：证据→引用、拒答判定、抽取式回答
api/          HTTP API：壳芯分离、错误翻译表、请求日志
evaluation/   评测指标（recall@k / MRR）+ 评测编排 + 消融实验
```

每层的契约（公开 API、边界规则、责任归属）详见配套文档 `PROJECT_LAYOUT.md`。

## 评测与消融

**评测指标**：文档级 `recall@k`（1~10）、`MRR`，冷/热耗时表（P50/P95）。

**消融结论**（100 篇语料 + 300 条手写 query，4 组单变量对照）：

| 组 | recall@1 | MRR | 边际贡献 |
|---|---|---|---|
| baseline（全开） | 0.833 | 0.899 | — |
| **bm25_only** | **0.910** | **0.950** | BM25 腿 +0.000 |
| dense_only | 0.833 | 0.899 | **dense 腿 −0.08** |
| **no_rerank** | **0.910** | **0.948** | **rerank −0.08** |

**结论**：当前 hashing 字面级 embedding 下，**rerank 是负资产（默认关闭），纯 BM25 / 融合不重排最稳**。hashing 不懂语义、把高频词当相似信号，在主题相邻的语料上区分度弱；BM25 的 idf 给罕见词高权重、能精准区分主题。换真语义 embedding 后，dense 腿与 rerank 需重新评估。

> 消融结论依赖语料特征——在措辞重叠更高的语料上（data），加权融合 α≈0.78 略优于纯 BM25；在术语专业的机器学习语料上（data2），纯 BM25 即最优。详见 `LEARNING_LOG.md` 第 19~20 轮记录。

## 目录结构

```text
项目/
├── pyproject.toml          # 构建配置、CLI 入口点、pytest 配置
├── README.md               # 本文件
├── .gitignore
├── configs/default.yaml    # 默认配置模板（值须与模型默认值一致）
├── data/                   # 语料与评测数据（后端分布式领域）
│   ├── raw/                # 100 篇中文技术文档（20 主题 × 5 篇，脚本生成）
│   └── eval/qrels.json     # 300 条手写 query + 相关文档标注
├── data2/                  # 第二套评测语料（机器学习领域）
│   ├── raw/                # 100 篇（20 主题 × 5 篇）
│   └── eval/qrels.json     # 300 条手写 query
├── reports/                # 评测报告落盘（eval.json / ablation.json）
├── scripts/                # 语料与评测集生成脚本
├── src/ragkit/             # 唯一被 import 的代码（分层见上）
└── tests/                  # 契约测试（268 条）
```

## 开发说明

- **代码放在 `src/ragkit/`**，测试在 `tests/`；改动 `pyproject.toml` 后须重新 `pip install -e ".[dev]"`。
- **测试即契约**：每层的公开 API、边界行为都由 `tests/` 锁定；改默认值、改契约都要同步测试。
- **`.env` 防范意识**：将来接 LLM 时 API Key 放 `.env`，绝不能提交进 Git。
- **可再生的重建优于修补**：`data/index/` 是 `ragkit build` 的产物，可随时重建；`data/raw/` 与 `data/eval/` 是语料与标注，值得进版本控制。

## 常见问题

| 现象 | 原因与处理 |
|---|---|
| `ModuleNotFoundError: No module named 'ragkit'` | 未执行可编辑安装，重新 `pip install -e ".[dev]"` |
| 命令行找不到 `ragkit` | 安装时没带 `-e`，或 `[project.scripts]` 未声明 |
| `ragkit ask` 提示"先运行 ragkit build" | 索引缺失或损坏，先执行 `ragkit build` |
| `ragkit eval` 全 0 | `data_dir` 与评测集 doc_id 口径不一致，确认 `data_dir = data/raw` |
| `Activate.ps1 无法加载` | 不必改执行策略，直接 `.\.venv\Scripts\python.exe` 调用 |
| 中文输出乱码 | 读写显式 `encoding="utf-8"`；可设 `PYTHONUTF8=1` |
| 安装 3.14 后依赖装不上 | 开发环境固定用 Python 3.12 |

## 路线图

| 状态 | 内容 |
|---|---|
| ✅ 已完成 | 骨架 → 领域模型/配置 → 加载/分块 → 向量化/向量库 → BM25/混合检索/融合/重排 → 建库 → 生成 → CLI → HTTP API → 评测 → 消融 |
| ⬜ 扩展（触发信号驱动） | 真语义 embedding（dense 腿重估）、cross-encoder rerank、`openai_compatible` 真实生成、增量更新、HTML/PDF 加载器、FastAPI 迁移、鉴权 |

## 说明

本项目是学习项目，目标是"能独立解释并重写每个核心模块"，而不是"尽快得到一个能跑的仓库"。每个阶段先写测试、再写实现；评测与消融结论如实记录，不隐瞒失败样本与已知局限。开发全程的决策、踩坑、通用规律见 `LEARNING_LOG.md`，系统契约见 `PROJECT_LAYOUT.md`。
