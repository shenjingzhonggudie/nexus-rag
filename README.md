# RAGKit

[![tests](https://github.com/shenjingzhonggudie/nexus-rag/actions/workflows/tests.yml/badge.svg)](https://github.com/shenjingzhonggudie/nexus-rag/actions/workflows/tests.yml)

中文文档检索与抽取式问答项目。仓库名为 `nexus-rag`，Python 包和命令名为 `ragkit`。未使用 LangChain 或 LlamaIndex；BM25、排名融合、规则拒答和检索指标在本项目中实现，向量计算使用 NumPy，BGE 模型通过 sentence-transformers 接入。

## 能力范围

- 加载 `.txt/.md/.markdown`，规范化后按标题或固定长度分块，建立 BM25 和向量索引。
- 支持 hashing 向量和可选 BGE 模型。默认新建索引使用 hashing；加载已有索引时以 manifest 记录的模型为准。
- `rerank_enabled=True` 使用加权排名融合，关闭时使用等权 RRF；当前没有 cross-encoder 重排。
- 回答为最高分块的原文，并附检索块引用；`openai_compatible` 生成接口尚未实现。
- 拒答依据英文标识符检查和实词覆盖率，不能可靠判断证据是否足以回答问题。

Python 要求 >= 3.11，本次使用 3.12.10。基础依赖为 `pyyaml`、`pydantic`、`jieba`、`numpy`。依赖与语料准备好后，hashing 路径无需联网或 API Key；BGE 离线运行还需要本地模型文件。

## 快速开始

在仓库根目录执行。以下示例使用独立目录，不覆盖 `data/index`：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

New-Item -ItemType Directory -Force data/demo | Out-Null
Set-Content -LiteralPath data/demo/example.md -Encoding utf8 -Value "容器镜像越小，拉取镜像的时间通常越短。"
@"
data_dir: data/demo
index_dir: data/index.demo
"@ | Set-Content -LiteralPath configs/demo.yaml -Encoding utf8

.\.venv\Scripts\ragkit.exe build --config configs/demo.yaml
.\.venv\Scripts\ragkit.exe ask "如何减少拉取容器镜像的时间？" --config configs/demo.yaml
.\.venv\Scripts\python.exe -m pytest -q
```

公开文档和开发评测题的使用方式见 [数据说明](data/README.md)。`data/raw/` 和索引未随仓库分发，不能在新克隆后直接运行默认建库、问答或评测。

### BGE

安装可选依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,embedding]"
```

准备自己的 YAML 配置，例如：

```yaml
data_dir: data/raw
index_dir: data/index.bge
embedding:
  provider: bge
  dim: 512
  model_name: BAAI/bge-small-zh-v1.5
```

保存为 `configs/bge.local.yaml` 后，使用 `build --config configs/bge.local.yaml` 建库，问答和服务也传入该配置。首次使用模型名可能联网下载；离线运行应先准备缓存或将 `model_name` 设为本地路径，并设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`。

`build` 会写入配置指定的索引目录；比较不同模型时使用不同目录。切换 YAML 中的 provider 不会转换已有向量，须重新建库。

## 命令和服务

| 命令 | 作用 | 参数 |
|---|---|---|
| `ragkit build` | 从文档建索引 | `--config`、`--root` |
| `ragkit ask QUERY` | 返回块原文和引用，或拒答提示 | `--config` |
| `ragkit serve` | 启动本地 HTTP API 和 Web UI | `--config`、`--host`、`--port` |
| `ragkit eval` | 运行题集并写 JSON 报告 | `--config`、`--qrels`、`--out` |

配置加载顺序为环境变量（`RAG__*`）> 显式指定的 YAML > 模型默认值；不传 `--config` 时不会自动读取 `configs/default.yaml`。`build --root` 单独覆盖语料目录，`serve --host/--port` 控制监听地址。相对路径按当前工作目录解析。

```powershell
.\.venv\Scripts\ragkit.exe serve --config configs/demo.yaml --port 8000
```

浏览器访问 `http://127.0.0.1:8000/`。服务启动时加载索引并尝试预热 embedding；预热失败会记日志，后续查询仍可能失败。接口如下：

| 接口 | 内容 |
|---|---|
| `GET /healthz` | 服务健康信息 |
| `POST /ask` | `{"query":"问题"}` → 抽取式回答、引用及拒答状态 |
| `POST /api/search` | 同样的请求体 → 检索块和分数 |
| `GET /api/knowledge` | 文档与块数 |
| `GET /api/chunks?doc=...` | 指定文档的块 |

CLI 拒答退出码为 0；用法错误通常为 2，已处理的配置或索引错误为 1。未处理异常的提示和退出行为不保证统一。

## 当前实测

2026-10-24在本地Python 3.12.10环境核验v2标注与判分。自动测试 **364 passed in 19.13s**，包含严格50%边界、区间并集去重、必要证据组合、CLI有答案命中和固定输出重评；开发集另运行了真实BGE检索。测试通过不等于回答质量已获验证。

本地 `data/index` 包含 100 篇文档、1553 个块，模型为 `BAAI/bge-small-zh-v1.5`，512 维。检索配置为两路候选上限各 20、加权融合 α=0.7、最终取 5，拒答阈值 0.05。声明配置默认 provider 是 hashing，实际 provider 由索引 manifest 覆盖，报告同时记录两者。

现有 **248道开发题**已重标为具体回答要点与最小充分证据：203道有答案、45道无答案，共320个要点、504段原文证据。3道原无答案题根据正文纠正，题干、ID和source未改；修订说明及哈希见 [标注说明](data/README.md)和 [manifest](data/eval/annotation_manifest.json)。证据长度中位数78.5字符，最长354字符。按来源统计有答案题：

| 来源 | 有答案题数 | 要点Recall@1 | @3 | @5 | 前缀MRR | 全部要点命中@5 |
|---|---:|---:|---:|---:|---:|---:|
| `internal`：读正文出题 | 103 | 0.460 | 0.645 | 0.704 | 0.6426 | 65/103（63.1%） |
| `external`：只看标题出题 | 100 | 0.295 | 0.380 | 0.440 | 0.3965 | 38/100（38.0%） |

无答案题正确拒答 **18/45（40.0%）**，其余27道未拒答；有答案题误拒 **2/203（约1.0%）**。当前拒答规则仍有明显漏拒。

本次保留现有语料与索引，仅重标题目、修改判分并重跑开发集；未重跑盲测和消融。

指标定义与限制：

- 前k块在同文档内取字符区间并集，每段必要证据的覆盖字符数须**严格超过证据长度的50%**；恰好50%不算。重复块不重复累计，中间空隙不计覆盖，同一要点的所有必要证据均须达标。
- 要点Recall@k先计算每题命中要点比例，再按题平均；全部要点命中率要求该题所有要点均命中。前缀MRR是前k块首次联合支持任一要点时的排名倒数，不要求支持全部要点。均只统计有答案题。
- 字符覆盖可能遗漏关键条件，不是语义充分性检查或回答正确率。标注经过AI辅助原文复核及机械校验，尚无独立人工验收。
- v2的标注、题型分母和判分均与旧版小节相交口径不同，新旧成绩不能直接比较。
- 默认 `final_k=5`，报告中的 @6～@10 与 @5 相同，不能据此判断前 10 个候选的召回能力。
- 248 道题已参与开发反馈；两种出题来源也不是训练/测试划分，均不能据此宣称独立泛化表现。

## 复现评测与消融

先准备与标注匹配的语料和索引，再运行：

```powershell
.\.venv\Scripts\python.exe scripts/check_qrels.py data/eval/qrels.json --strict
.\.venv\Scripts\ragkit.exe eval --qrels data/eval/qrels.json --out reports/eval.json
.\.venv\Scripts\python.exe demo_ablation.py --index-dir data/index --out reports/ablation.json
```

`demo_ablation.py` 比较默认加权融合、α=0.9、α=0.5、等权 RRF、BM25 单路和 dense 单路，使用脚本内的默认检索配置。报告应随代码、题集、索引与有效配置一起解释；本次未重跑消融，不沿用旧数字断言某组件或参数最优。

## 盲测结果（2026-10-23，2026-10-24重评）

原实验代码 `80b6aea`。本次先只看题干和原文重标62题，在提交 [`b63d485`](https://github.com/shenjingzhonggudie/nexus-rag/commit/b63d485) 冻结并推送答案后，才打开两份原检索报告，保留原检索顺序重评，未重跑模型。

重标后为43道完整可答、17道无答案、2道待复核。3道原无答案题有明确的限定回答，已记录更正理由；2道题分别存在原文内部冲突、默认值未写明的问题。主要指标只统计43道已定稿可答题：

| 配置 | 要点Recall@5 | 前缀MRR | 全部要点命中@5 | 无答案正确拒答 |
|---|---:|---:|---:|---:|
| BGE＋加权融合 | 0.913 | 0.8605 | 36/43（83.7%） | **0/17** |
| hashing＋等权 RRF | 0.855 | 0.7558 | 34/43（79.1%） | **0/17** |

- 每段必要证据须由前k块联合覆盖**严格超过50%**，恰好50%不算；同一要点的所有必要证据均须达标。将2道待复核题按未完整覆盖计入45题分母后，保守整题命中率为80.0%和75.6%。
- 旧报告没有最终回答正文，只能重评检索证据覆盖，不能据此报告回答正确率；仅首块就覆盖全部要点的比例为24/43（55.8%）和21/43（48.8%）。
- 新旧标注、分母和判分不同，不能直接比较；样本少、题型与开发集不同，且已用于开发反馈，这次重评不是新的独立盲测。

**两组对17道无答案题仍全部漏拒。** [重标、冻结、逐题覆盖与复现方法](experiments/holdout-evidence-v2/README.md)另存；[原始归档](experiments/holdout-v1/README.md)保持不变。

## 代码与文档

```text
文档 → loaders → chunking → embeddings → index / stores
问题 → BM25 + dense → 加权排名融合或等权 RRF → 拒答 → 块原文与引用
题集 → 检索 → 回答要点的必要证据联合覆盖 → 分组指标
```

[模块契约](docs/PROJECT_LAYOUT.md) · [协作指南](AGENTS.md) · [项目概览](docs/SUMMARY.md) · [历史开发记录](docs/LEARNING_LOG.md) · [数据来源](data/SOURCES.md)
