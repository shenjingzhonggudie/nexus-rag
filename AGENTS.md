# AGENTS.md — RAGKit 项目交接指南

> 给下一个接手此项目的 AI agent / 开发者：先读本文，再动手。关键结论和约定都在这里，避免重复踩坑。

## 项目是什么

从零手搓的**中文 RAG 系统**（检索增强生成），**不用 LangChain/LlamaIndex 等框架**，核心算法（BM25、RRF/加权融合、重排、拒答、评测指标）全部自己实现。默认模式**离线可运行、不需要 API Key、不联网**。

- 版本：`1.0.0`（`src/ragkit/__init__.py` 的 `__version__`）
- 测试：**272 条全绿**（`pytest -q`）
- Python：3.12（虚拟环境 `.venv`）
- GitHub：`https://github.com/shenjingzhonggudie/nexus-rag`（分支 `master`）

## 技术栈与依赖

`pyyaml` / `pydantic` / `jieba`（中文分词）/ `numpy`。**零 RAG 框架、零真 embedding 模型**——向量用的是 hashing 字面级 embedding（见"关键结论"）。

## 怎么跑

```powershell
cd "C:\Users\王佳浩\Desktop\项目"
.\.venv\Scripts\python.exe -m pytest -q          # 跑测试（预期 272 passed）
.\.venv\Scripts\ragkit.exe build                  # 建库（data/raw → data/index）
.\.venv\Scripts\ragkit.exe ask "问题"             # 问答
.\.venv\Scripts\ragkit.exe serve --port 8000      # HTTP API（POST /ask、GET /healthz）
.\.venv\Scripts\ragkit.exe eval                   # 评测（落盘 reports/eval.json）
```

> 不要用 `py -3.14`（部分依赖无预编译包）；venv 直接用 `.\.venv\Scripts\python.exe`，不必 activate。

## 架构（九层，都在 `src/ragkit/` 下）

| 层 | 目录 | 职责 |
|---|---|---|
| 加载 | `loaders/` | `.txt/.md/.markdown`，UTF-8 + GBK 回退，坏文件隔离 |
| 分块 | `chunking/` | heading（按 `##`，超长小节 fixed 再切）+ fixed，稳定 chunk_id（内容哈希） |
| 向量化 | `embeddings/` | hashing 字面级 embedding，L2 归一化 |
| 存储 | `stores/` | NumPy 向量库，五文件落盘（manifest 最后写） |
| 检索 | `retrieval/` | BM25 → dense → 融合（RRF/加权）→ rerank |
| 建库 | `index/` | `build` / `load_index`，chunks.jsonl + id 一致性校验 |
| 生成 | `generation/` | `answer_question`：证据→引用、拒答、抽取式回答 |
| API | `api/` | `create_server` / `_answer_payload`（壳芯分离） |
| 评测 | `evaluation/` | recall@k / MRR + 评测编排 + 消融 |

## 关键结论（**不要轻易推翻，都是消融实验验证过的**）

1. **融合默认是加权 RRF**：`RetrievalConfig.fusion = "weighted"`、`fusion_alpha = 0.9`。公式 `S(d) = 0.9·S1 + 0.1·S2`，其中 `S_i = 1/(60 + rank_i)`。
2. **rerank 默认关闭**（`rerank_enabled=False`）——`baseline == dense_only` 印证 rerank 用 dense 余弦一票否决，这个规律跨语料稳定。
3. **dense 腿（hashing）是字面级替身，不懂语义**：这是 hashing 的固有限制，不是 bug——要真正提升 dense 腿，得接真 embedding（BGE 等）。
4. **块级标注下（10 篇 + 25 条 query）的完整消融结果**：

| 组 | @1 | @2 | @3 | @4 | @5 | @6 | @7 | @8 | @9 | @10 | MRR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline（等权 RRF + dense rerank） | 0.25 | 0.29 | 0.40 | 0.42 | 0.43 | 0.43 | 0.43 | 0.43 | 0.43 | 0.43 | 0.428 |
| bm25_only（纯 BM25） | 0.25 | 0.31 | 0.37 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | 0.447 |
| dense_only（纯 dense） | 0.25 | 0.29 | 0.40 | 0.42 | 0.43 | 0.43 | 0.43 | 0.43 | 0.43 | 0.43 | 0.428 |
| **no_rerank（等权 RRF）** | **0.27** | **0.35** | 0.41 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | **0.477** |
| weighted α=0.9（当前默认） | 0.25 | 0.33 | 0.41 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | 0.457 |

   no_rerank（等权 RRF）MRR 最高（0.477），weighted α=0.9（0.457）略低但差异在样本波动内——25 条样本太小，不据此断言"等权优于加权"，要下结论需扩大样本 + 显著性检验。
5. **标注粒度决定任务难度**：文档级 0.9（在 N 篇里选主题）vs 块级 0.25（在 M 块里选段落），跨粒度比较绝对数字没有意义。

## 必须遵守的约定（改代码前先读）

- **测试即契约**：改默认值、改公开 API、改边界行为，必须同步 `tests/` 里的对应测试。`pytest -q` 必须全绿。
- **配置对象进、领域对象出**：`search` 收 `RetrievalConfig`、`answer_question` 收 `LLMConfig`，不传散参数。
- **壳芯分离**：HTTP 的 `_answer_payload` 是纯函数芯，handler 只做 HTTP 细节；CLI 是薄壳，不写业务逻辑。
- **领域层输出结构化对象，表现层各自翻译**：领域层产出 `Chunk`/`RetrievalResult`/`Answer`，CLI 转文本、API 转 JSON，不在领域层写格式化。
- **参数可注入 = 测试可隔离**：`main(argv, environ)`、`load_config(environ)` 不直接读 `sys.argv`/`os.environ`。
- **可再生的重建优于修补**：`data/index/`、`reports/` 是产物（已被 `.gitignore` 忽略），可随时重建；`data/raw/`、`data/eval/` 是原料，要保留。
- **改 `pyproject.toml` 后要重新 `pip install -e ".[dev]"`**（离线环境装依赖需联网或预装 setuptools）。

## 数据文件说明

| 路径 | 内容 | 可否再生 |
|---|---|---|
| `data/raw/` | 语料：10 篇后端技术文档（2 主题 × 1正+4误导，每篇约 10000 字） | ✅ `python scripts/generate_corpus.py` |
| `data/eval/qrels.json` | 评测集：25 条 query（direct/paraphrase/no_answer）+ 块级标注 | ✅ 同脚本 |
| `data/index/`、`reports/` | 建库/评测产物 | ✅ 可重建，已 gitignore |

> 生成脚本在 `scripts/`，数据源是 `scripts/corpus_data_01.py` / `corpus_data_02.py`（语料内容 + query）。改语料/评测集改这些源文件，再跑 `generate_corpus.py`，别直接手改 `data/raw`。

## 文档索引

- `README.md`：项目入口（四命令、架构、消融结论）
- `docs/PROJECT_LAYOUT.md`：**各层契约**（公开 API、边界规则、责任归属）——改代码前查这里
- `docs/LEARNING_LOG.md`：24 轮开发记录（决策、踩坑、通用规律）——理解"为什么这么设计"查这里
- `docs/SUMMARY.md`：总结报告（架构全景 + 消融结论 + 规律提炼）
- `LICENSE`：MIT

## 待办 / 扩展项（都有触发信号，不是"应该做"而是"信号到了再做"）

| 项 | 触发信号 |
|---|---|
| 真语义 embedding（替换 hashing，dense 腿重估） | 拿到 embedding 模型（本地 BGE）或 API key |
| cross-encoder rerank | 接真模型后重评 rerank |
| `openai_compatible` 真实生成 | 拿到 LLM API key（`generation/answer.py` 已有 fail-fast 分支，只改函数体） |
| 增量更新 | 全量重建慢到痛 |
| HTML/PDF 加载器 | 真实需要处理这些格式 |
| FastAPI 迁移 / 鉴权 | 需要 OpenAPI 文档或暴露公网 |

## 给接手者的三个提醒

1. **别动消融结论除非有新的实测数据**——当前结论是 25 条块级标注 query 上跑出来的（样本较小），改动默认配置前先重跑 `demo_ablation.py` 或扩大样本重测。
2. **中文引号/编码**：源码和文档统一 UTF-8；写文档里的中文引号别用英文双引号（历史上引发过语法错误）。
3. **GitHub 网络**：push 可能因网络连不上 `github.com:443` 失败（国内直连常被墙），本地 commit 不会丢，等网络恢复或开代理再 `git push`。
