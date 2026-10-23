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

2026-10-23 在本地 Python 3.12.10 环境核验，代码基线为 `7553d86`。自动测试结果为 **279 passed in 12.49s**；测试通过不代表所有模型路径和回答质量均已覆盖。现有 CLI 评测测试有旧格式夹具，未验证有答案题的正确命中；此次另外运行了真实 BGE 检索。

本地 `data/index` 包含 100 篇文档、1553 个块，模型为 `BAAI/bge-small-zh-v1.5`，512 维。检索配置为两路候选上限各 20、加权融合 α=0.7、最终取 5，拒答阈值 0.05。声明配置默认 provider 是 hashing，实际 provider 由索引 manifest 覆盖，报告同时记录两者。

以下为已有 **248 道开发题**的结果：200 道有答案、48 道无答案。按来源统计有答案题：

| 来源 | 有答案题数 | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---:|---:|---:|---:|---:|
| `internal`：读正文出题 | 100 | 0.550 | 0.695 | 0.765 | 0.6835 |
| `external`：只看标题出题 | 100 | 0.390 | 0.480 | 0.560 | 0.4485 |

无答案题正确拒答 **18/48（37.5%）**，其余 30 道未拒答；有答案题误拒 **2/200（1.0%）**。这说明当前拒答规则在本题集上仍有明显漏拒。

后续查询检索阶段 P50 为 39.6 ms、P95 为 52.6 ms；首查为 25.93 秒。首查指标包含首次检索的模型加载开销，不含之前的解释器启动和索引加载；这些数值仅代表本机本次运行。

指标定义与限制：

- 命中是“同文档、检索块与答案字符区间相交”，不要求包含完整答案。
- Recall@k 是前 k 个块覆盖的答案小节比例；MRR 是首个命中块的排名倒数。二者仅统计有答案题，不能解释为最终回答正确率。
- 默认 `final_k=5`，报告中的 @6～@10 与 @5 相同，不能据此判断前 10 个候选的召回能力。
- 248 道题已参与开发反馈；两种出题来源也不是训练/测试划分，均不能据此宣称独立泛化表现。
- 本地 editable 安装元数据仍为 0.0.1，源码和 `pyproject.toml` 为 1.0.0；导入位置已确认是本项目源码。

## 复现评测与消融

先准备与标注匹配的语料和索引，再运行：

```powershell
.\.venv\Scripts\python.exe scripts/check_qrels.py data/eval/qrels.json
.\.venv\Scripts\ragkit.exe eval --qrels data/eval/qrels.json --out reports/eval.json
.\.venv\Scripts\python.exe demo_ablation.py --index-dir data/index --out reports/ablation.json
```

`demo_ablation.py` 比较默认加权融合、α=0.9、α=0.5、等权 RRF、BM25 单路和 dense 单路，使用脚本内的默认检索配置。报告应随代码、题集、索引与有效配置一起解释；本次未重跑消融，不沿用旧数字断言某组件或参数最优。

## 盲测结果（2026-10-23）

被测代码 `80b6aea`，共62题（42道可回答、20道同领域无答案）。Recall/MRR 仅统计可回答题。

| 配置 | Recall@5 | MRR | 无答案正确拒答 |
|---|---:|---:|---:|
| BGE＋加权融合 | 0.964 | 0.893 | **0/20** |
| hashing＋等权 RRF | 0.929 | 0.831 | **0/20** |

- 指标衡量小节区间命中，不是回答正确率。
- 样本较少、题型构成不同，不能直接与开发集比较。
- 该集已进入开发反馈循环，后续成绩属于回归表现。

**这次盲测中检索命中较高，但20道无答案题全部漏拒。** 完整流程和明细见 [experiments/holdout-v1/](experiments/holdout-v1/README.md)。

## 代码与文档

```text
文档 → loaders → chunking → embeddings → index / stores
问题 → BM25 + dense → 加权排名融合或等权 RRF → 拒答 → 块原文与引用
题集 → 检索 → 字符区间命中 → 分组指标
```

[模块契约](docs/PROJECT_LAYOUT.md) · [协作指南](AGENTS.md) · [项目概览](docs/SUMMARY.md) · [历史开发记录](docs/LEARNING_LOG.md) · [数据来源](data/SOURCES.md)
