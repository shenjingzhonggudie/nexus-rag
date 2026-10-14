# RAGKit

从零手搓的中文技术文档问答系统（RAG），用于学习与工程实践。

**设计前提**：不使用 LangChain、LlamaIndex 等 RAG 框架。检索、融合、重排、拒答、评测等核心算法全部自己实现，默认模式**离线可运行、不需要 API Key、不联网**；真实向量模型与 LLM 只作为可选适配器接入。

## 当前状态

**第 0 阶段：项目骨架，尚无任何 RAG 功能。**

已完成：

- `src` 布局的可安装、可测试 Python 项目骨架；
- `ragkit` 命令行入口（目前仅支持 `--help` 与 `--version`）；
- 3 条冒烟测试，验证包可导入、CLI 可调用。

未完成：文档加载、分块、向量化、检索、拒答、生成、评测、API 等全部后续能力。**当前版本不能问答**。

| 项 | 值 |
|---|---|
| 版本 | 0.0.1 |
| Python | >= 3.11（开发环境使用 3.12） |
| 运行平台 | 主要面向 Windows + PowerShell，代码本身跨平台 |

## 快速开始

```powershell
# 1. 进入项目目录
cd "C:\Users\王佳浩\Desktop\项目"

# 2. 创建虚拟环境（用 3.12；不要用 3.14，部分依赖可能缺少预编译包）
py -3.12 -m venv .venv

# 3. 可编辑安装（-e 表示不复制代码，只写路径映射；.[dev] 一并装开发依赖 pytest）
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

> 为什么不先激活虚拟环境？PowerShell 的默认执行策略可能禁止运行 `Activate.ps1`，直接调用 `.\.venv\Scripts\python.exe` 效果相同，且不必改动系统设置。

### 验收命令

在项目根目录执行，三条都应成功：

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # 预期：3 passed
.\.venv\Scripts\ragkit.exe --help                # 预期：第一行直接是 usage: ragkit
.\.venv\Scripts\ragkit.exe --version             # 预期：ragkit 0.0.1
```

如果 `ragkit` 命令找不到，或 `import ragkit` 报 `ModuleNotFoundError`，说明可编辑安装没生效，重新执行第 3 步。

## 目录结构

```text
项目/
├── pyproject.toml          # 构建配置、项目元信息、CLI 入口点、pytest 配置
├── README.md               # 本文件
├── .gitignore              # 忽略 .venv/、__pycache__/、.egg-info/、.env 等
├── .venv/                  # 虚拟环境（不入 git，可由上面命令重建）
├── src/
│   └── ragkit/             # 唯一要发布、要被 import 的代码
│       ├── __init__.py     # 包文档字符串与 __version__
│       └── cli.py          # 命令行入口：main(argv) -> int
└── tests/
    └── test_smoke.py       # 冒烟测试：导入、--version、无参数与 --help 行为
```

`src/` 本身不是包（没有 `__init__.py`），它只是存放包的目录。`pyproject.toml` 里的 `where = ["src"]` 把它设为安装工具的搜索根，因此导入名是 `ragkit` 而不是 `src.ragkit`。

后续阶段将逐步增加 `configs/`、`data/`、`reports/`、`scripts/`、`tests/` 下的更多内容，以及 Dockerfile 与 CI 配置。

## 开发说明

- **代码放在 `src/ragkit/` 下**，测试放在 `tests/` 下，两者都在 `src` 内外分界线的两侧：前者会被发布，后者不会。
- **改动 `pyproject.toml` 后必须重新安装**（`pip install -e ".[dev]"`）。可编辑安装只在 site-packages 里写路径映射，改了配置不会自动同步。
- **提交前自查**：`git status` 里不应出现 `.venv/`、`__pycache__/`、`*.egg-info/`、`.env`。
- **`.env` 现在就要建立防范意识**：第 10 阶段接入 LLM 时会在这里放 API Key，一旦提交进 Git 历史就很难彻底清除。

## 常见问题

| 现象 | 原因与处理 |
|---|---|
| `ModuleNotFoundError: No module named 'ragkit'` | 未执行可编辑安装；或 `pyproject.toml` 里 `where = ["src"]` 缺失；或 `src/ragkit/__init__.py` 不存在 |
| 命令行找不到 `ragkit` | 安装时没带 `-e`；或 `[project.scripts]` 未声明。安装成功后可在 `.venv\Scripts\ragkit.exe` 找到 |
| `Activate.ps1 无法加载，因为在此系统上禁止运行脚本` | 不必改执行策略，直接用 `.\.venv\Scripts\python.exe` 调用 |
| 中文输出乱码 | 读写文本时显式指定 `encoding="utf-8"`；控制台问题可设置环境变量 `PYTHONUTF8=1` |
| 安装了 3.14 后依赖装不上 | 本项目开发环境固定用 Python 3.12 |

## 路线图

| 阶段 | 内容 |
|---|---|
| 0 | 项目骨架、可安装、可测试 |
| 1 | 领域模型（Document / Chunk / ScoredChunk / Citation / Answer / RetrievalTrace）与配置系统 |
| 2-3 | 文本清洗与分词、文件加载、多种分块策略 |
| 4-5 | 本地 hashing embedding、NumPy 向量库 |
| 6-7 | 自研 BM25、混合检索、融合与重排 |
| 8-9 | 增量索引与持久化、拒答、抽取式回答与引用 |
| 10-12 | 可选 LLM 生成、RAGEngine 与 CLI、FastAPI + SSE |
| 13-14 | 评测集与指标、消融实验与参数选择 |
| 15 | Docker、CI、安全边界与交付文档 |

## 说明

本项目是学习项目，目标是"能独立解释并重写每个核心模块"，而不是"尽快得到一个能跑的仓库"。因此每个阶段都会先写测试、再写实现，评测与消融结论如实记录，不隐瞒失败样本与已知局限。
