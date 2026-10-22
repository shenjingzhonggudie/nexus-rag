# AGENTS.md — RAGKit 项目交接指南

> 给下一个接手此项目的 AI agent / 开发者：先读本文，再动手。关键结论和约定都在这里，避免重复踩坑。

## 项目是什么

从零手搓的**中文 RAG 系统**（检索增强生成），**不用 LangChain/LlamaIndex 等框架**，核心算法（BM25、RRF/加权融合、重排、拒答、评测指标）全部自己实现。默认模式**离线可运行、不需要 API Key、不联网**。

- 版本：`1.0.0`（`src/ragkit/__init__.py` 的 `__version__`）
- 测试：**278 条全绿**（`pytest -q`）
- Python：3.12（虚拟环境 `.venv`）
- GitHub：`https://github.com/shenjingzhonggudie/nexus-rag`（分支 `master`）

## 技术栈与依赖

`pyyaml` / `pydantic` / `jieba`（中文分词）/ `numpy`。**零 RAG 框架**；默认向量是
hashing 字面级 embedding（离线零依赖）。真语义模型是**可选依赖组**：
`pip install -e ".[embedding]"` 后才启用 `embedding.provider = bge`（见"关键结论"）。

## 怎么跑

```powershell
cd path/to/nexus-rag                             # 换成你 clone 下来的目录
.\.venv\Scripts\python.exe -m pytest -q          # 跑测试（预期 278 passed）
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
| 向量化 | `embeddings/` | hashing 字面级（默认）/ bge 本地语义模型（可选依赖组 `.[embedding]`） |
| 存储 | `stores/` | NumPy 向量库，五文件落盘（manifest 最后写，内含 provider 自描述） |
| 检索 | `retrieval/` | BM25 → dense → 融合（RRF/加权）→ rerank；`match_score` 供拒答 |
| 建库 | `index/` | `build` / `load_index`，chunks.jsonl + id 一致性校验 |
| 生成 | `generation/` | `answer_question`：证据→引用、**两类拒答**、抽取式回答 |
| API | `api/` | `create_server` / `_answer_payload`（壳芯分离） |
| 评测 | `evaluation/` | 覆盖式 recall@k / MRR + 拒答指标 + **小节级标注（区间重叠）** + 消融 |

## 关键结论（**不要轻易推翻**）

1. **融合 = 加权排名融合，在 `rerank()` 里实现**：`S(d) = α·S1(d) + (1−α)·S2(d)`，`S_i = 1/(60 + rank_i)`，`fusion_alpha = 0.7`（BM25 权重 0.7 / dense 权重 0.3）。**`weighted_fuse` 已删除**——加权融合属于精排阶段职责，与等权 `rrf_fuse` 分开，避免两份几乎相同的实现。默认值 0.7 是在 221 条上调出来的（见第 2 条）。
2. **`rerank_enabled` 默认 `True`（加权融合）**：1553 块索引上 MRR **0.458**（α=0.7）vs **0.454**（等权 RRF），加权略优；`@5` 则是等权更高（0.549 vs 0.539）。α 的敏感度不大（MRR 0.436~0.458），**真正的瓶颈是 embedding**：`dense_only` 的 MRR 从 hashing 0.300 升到 bge 0.438。
3. **hashing dense 是字面级替身，不懂语义**：1553 块索引上它几乎无贡献（`bm25_only` MRR **0.508** 高于任何融合组）——字面哈希会把"词面像但无关"的块排上来。**已接入 BGE**（`embeddings/bge.py`，可选依赖组 `.[embedding]`）：dense 腿从 **−0.007 转正到 +0.054**，`dense_only` 的 MRR 从 **0.300 升到 0.438**。
4. **标注绝不绑切分**（本轮最重要的约定）：答案标「文档 + 小节字符区间」，评测用**区间重叠**判定。千万不要改成标 `chunk_id`——切分策略一改就全废。
5. **拒答是两层判据**：① `unknown_entities`——查询里首字母大写的英文专有名词（Kafka / JVM）若语料中从未出现，**强制 `match_score=0`**；② 实词 idf 加权覆盖率低于阈值（默认 0.05）。稠密腿永远返回 top_k，所以"结果为空"根本不成立；融合分也不能当阈值（排名分 0.012~0.017）。实测：拒答准确率 100%、误拒率 0.5%。**`v-model` / `v-if` 这类小写框架指令不能当外来实体**，否则会稳定误拒正常问题。
6. **评测必须按来源分组报告**：`internal`（读正文出题，**能力基准**，recall@1=0.410 / MRR=0.529）与 `external`（只看标题出题，**真实用户视角**，recall@1=0.340 / MRR=0.389）**并列报告，不报合计**——合计取决于两组题目比例，不是系统能力。对内外一致：README、`eval` 输出、面试话术都一样。

> **消融（218 条标注，1553 块索引，6 组）**：`baseline`（α=0.7）/ `alpha_09` / `alpha_05` /
> `no_rerank`（等权 RRF）/ `bm25_only` / `dense_only`，`test_ablation.py` 锁定。
> **自洽性检查**：`alpha_05` 与 `no_rerank` 每列完全相同（α=0.5 的加权就是等权 RRF）。
> 边际贡献（recall@1）：dense 腿 **hashing +0.003 / bge +0.092**；BM25 腿 +0.150 / +0.090；
> rerank **+0.028 / +0.018**。完整数字见 README「评测与消融」（两张表）。

## 必须遵守的约定（改代码前先读）

- **测试即契约**：改默认值、改公开 API、改边界行为，必须同步 `tests/` 里的对应测试。`pytest -q` 必须全绿。
- **配置对象进、领域对象出**：`search` 收 `RetrievalConfig`、`answer_question` 收 `LLMConfig`，不传散参数。
- **壳芯分离**：HTTP 的 `_answer_payload` 是纯函数芯，handler 只做 HTTP 细节；CLI 是薄壳，不写业务逻辑。
- **领域层输出结构化对象，表现层各自翻译**：领域层产出 `Chunk`/`RetrievalResult`/`Answer`，CLI 转文本、API 转 JSON，不在领域层写格式化。
- **参数可注入 = 测试可隔离**：`main(argv, environ)`、`load_config(environ)` 不直接读 `sys.argv`/`os.environ`。
- **可再生的重建优于修补**：`data/index/`、`reports/` 是产物（gitignore），可随时重建；`data/raw/` 是第三方正文（gitignore，由脚本拉取）；**只有 `data/eval/` 与 `data/SOURCES.md` 是必须保留的人工成果**。
- **改 `pyproject.toml` 后要重新 `pip install -e ".[dev]"`**（离线环境装依赖需联网或预装 setuptools）。

## 数据文件说明

| 路径 | 内容 | 可否再生 |
|---|---|---|
| `data/raw/` | 公开技术文档正文（K8s / TiDB / Vue / React） | ✅ `python scripts/fetch_docs.py`（需联网） |
| `data/eval/qrels.json` | 小节级标注：文档 + 字符区间（218 条，五类配比） | ❌ 人工筛选的成果，**必须提交** |
| `data/eval/qrels.example.json` | 五类标注的格式示例 | — |
| `data/SOURCES.md` | 数据来源与许可证 | ❌ fetch 时生成，**必须提交** |
| `data/index/`、`reports/` | 建库/评测产物 | ✅ 可重建，已 gitignore |

> 数据工具在 `scripts/`：`fetch_docs.py`（拉正文）/ `section_index.py`（列小节
> 与字符区间）/ `gen_queries.py`（生成出题 prompt）/ `check_qrels.py`（质检）。
> 完整流程见 `data/README.md`。**别把 `data/raw/` 的正文提交进 Git**——那是第三方
> 文档，再分发涉及许可证。

## 文档索引

- `README.md`：项目入口（四命令、架构、消融结论）
- `docs/PROJECT_LAYOUT.md`：**各层契约**（公开 API、边界规则、责任归属）——改代码前查这里
- `docs/LEARNING_LOG.md`：24 轮开发记录（决策、踩坑、通用规律）——理解"为什么这么设计"查这里
- `docs/SUMMARY.md`：总结报告（架构全景 + 消融结论 + 规律提炼）
- `LICENSE`：MIT

## 待办 / 扩展项（都有触发信号，不是"应该做"而是"信号到了再做"）

| 项 | 触发信号 |
|---|---|
| cross-encoder rerank | 接真模型后重评 rerank |
| `openai_compatible` 真实生成 | 拿到 LLM API key（`generation/answer.py` 已有 fail-fast 分支，只改函数体） |
| 增量更新 | 全量重建慢到痛 |
| HTML/PDF 加载器 | 真实需要处理这些格式 |
| FastAPI 迁移 / 鉴权 | 需要 OpenAPI 文档或暴露公网 |

## 给接手者的三个提醒

1. **消融数字已作废、方法论有效**——旧数字跑在已删除的合成语料上，别再引用；方向性结论（rerank 负贡献、hashing 只懂字面）保留，新语料到位后先重跑 `demo_ablation.py` 再报数。
2. **中文引号/编码**：源码和文档统一 UTF-8；写文档里的中文引号别用英文双引号（历史上引发过语法错误）。
3. **GitHub 网络**：push 可能因网络连不上 `github.com:443` 失败（国内直连常被墙），本地 commit 不会丢，等网络恢复或开代理再 `git push`。
