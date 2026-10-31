# RAGKit

[![tests](https://github.com/shenjingzhonggudie/nexus-rag/actions/workflows/tests.yml/badge.svg)](https://github.com/shenjingzhonggudie/nexus-rag/actions/workflows/tests.yml)

中文文档检索与抽取式问答项目。仓库名为 `nexus-rag`，Python 包和命令名为 `ragkit`。未使用 LangChain 或 LlamaIndex；BM25、排名融合、规则拒答和检索指标在本项目中实现，向量计算使用 NumPy，BGE embedding 和可选 cross-encoder 通过 sentence-transformers 接入。

## 能力范围

- 加载 `.txt/.md/.markdown`，规范化后按标题或固定长度分块，建立 BM25 和向量索引。
- 支持 hashing 向量和可选 BGE 模型。默认新建索引使用 hashing；加载已有索引时以 manifest 记录的模型为准。
- 融合由 `retrieval.fusion_method` 选择加权 RRF 或等权 RRF；独立的 cross-encoder 重排由 `rerank.enabled` 控制，默认启用并仅使用本地模型文件。
- 回答为最高分块的原文，并附检索块引用；`openai_compatible` 生成接口尚未实现。
- 拒答依据英文标识符检查和实词覆盖率，不能可靠判断证据是否足以回答问题。

Python 要求 >= 3.11，本次使用 3.12.10。基础依赖为 `pyyaml`、`pydantic`、`jieba`、`numpy`。依赖与语料准备好、并关闭模型重排后，hashing 路径无需联网或 API Key；保留默认重排时还需 `[rerank]` 依赖和本地重排权重，BGE embedding 也需要各自的依赖与模型文件。

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
rerank:
  enabled: false
"@ | Set-Content -LiteralPath configs/demo.yaml -Encoding utf8

.\.venv\Scripts\ragkit.exe build --config configs/demo.yaml
.\.venv\Scripts\ragkit.exe ask "如何减少拉取容器镜像的时间？" --config configs/demo.yaml
.\.venv\Scripts\python.exe -m pytest -q
```

此 hashing 小示例显式关闭模型重排，不需要下载权重。公开文档和开发评测题的使用方式见 [数据说明](data/README.md)。`data/raw/`、索引和模型权重均未随仓库分发，不能在新克隆后直接运行默认建库、问答或评测。

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

### 模型重排（默认启用）

重排默认启用；安装依赖并准备本地模型缓存或模型目录后即可使用。公开仓库不包含权重，新机器须安装 `[rerank]` 并下载模型，或在配置中显式设置 `rerank.enabled: false`。重排使用 [CrossEncoder 的成对评分接口](https://sbert.net/docs/package_reference/cross_encoder/model.html)，默认模型见 [BAAI/bge-reranker-base](https://huggingface.co/BAAI/bge-reranker-base)：

2026-10-25在本机安装依赖和6个模型文件，并改为默认启用；安装当时未运行模型。2026-10-26按新授权完成真实模型对照评测，结果见下文。重排权重修订为 `2cfc18c9415c912f9d8155881c133215df768a70`。

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,rerank]"
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='BAAI/bge-reranker-base', allow_patterns=['config.json','model.safetensors','sentencepiece.bpe.model','special_tokens_map.json','tokenizer.json','tokenizer_config.json'], max_workers=2)"
```

配置示例见 [rerank.example.yaml](configs/rerank.example.yaml)：

```yaml
retrieval:
  top_k: 20
  final_k: 5
  fusion_method: weighted_rrf
  fusion_alpha: 0.7
rerank:
  enabled: true
  model_name: BAAI/bge-reranker-base  # 支持中英；也可设为本地模型目录
  batch_size: 16
  max_length: 512
  device: cpu
  local_files_only: true
```

`rerank.enabled` 默认是 true，其他默认值如上。上述下载命令把推理所需文件写入默认 Hugging Face 缓存，避免下载其他格式的重复权重；也可把 `model_name` 设为已准备好的本地模型目录。`local_files_only=true` 保证运行重排时只使用本地已有文件；仅安装依赖不会下载模型，缓存未准备好时默认查询会明确报错。暂不使用模型时设置 `rerank.enabled: false`；加载、打分失败均不会静默退回融合排序。

查询流程为两路各取 top_k → 按 chunk_id 融合去重、取 top_k → 可选 cross-encoder → 取 final_k。重排把问题与候选块成对输入模型，以原始相关性 logit 排序；可负且不是概率，query 与块合计超过 max_length 个 token 会截断。融合分、模型 logit 和独立的 BM25 拒答 match_score 含义不同。

旧配置 `retrieval.rerank_enabled: true/false` 会发出弃用警告，分别映射到 `fusion_method: weighted_rrf/rrf`，新快照不再保留旧字段。迁移时删除旧键并写明 fusion_method；如同时提供冲突值会报错。旧键只控制融合方式，不改变顶层 `rerank.enabled`；模型开关跟随该独立配置，当前默认 true。需要关闭模型时显式设置 `rerank.enabled: false`。

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

## 新流程实测（2026-10-26）

在生产代码 `0e191f7` 上实际运行 BM25＋BGE 召回 → 加权融合 → `BAAI/bge-reranker-base` 重排。同版本关闭重排作对照，唯一配置差异为 `rerank.enabled`；保留现有题目、答案与索引，不据结果调参。共310题、两组620次查询，已用独立字符集合算法复算全部逐题覆盖及汇总指标。

**本表两组均使用v2证据覆盖口径，只比较同版本的重排开关。不得与v1“任意小节相交”的旧Recall数值比较涨跌。**

固定索引为100篇文档、1553块，embedding为 `BAAI/bge-small-zh-v1.5`（512维）；每路召回20块、加权融合 α=0.7 后保留20个候选，最终取5块，拒答阈值0.05。

| 题集/来源（可答题数） | 配置 | 要点Recall@1 | @3 | @5 | 前缀MRR | 全部要点命中@5 |
|---|---|---:|---:|---:|---:|---:|
| 开发 internal（103） | 仅融合 | 0.460 | 0.645 | 0.704 | 0.6426 | 65/103 |
| 开发 internal（103） | 融合＋重排 | 0.559 | 0.744 | 0.778 | 0.7484 | 74/103 |
| 开发 external（100） | 仅融合 | 0.295 | 0.380 | 0.440 | 0.3965 | 38/100 |
| 开发 external（100） | 融合＋重排 | 0.330 | 0.455 | 0.495 | 0.4387 | 45/100 |
| 留出集回归（43） | 仅融合 | 0.661 | 0.890 | 0.913 | 0.8605 | 36/43 |
| 留出集回归（43） | 融合＋重排 | 0.748 | 0.878 | 0.919 | 0.8922 | 37/43 |

**本轮重排改善开发集的证据排序，回归集Recall@5仅小幅提高、Recall@3略降；拒答表现没有改善。** 两组开发集均正确拒答18/45、误拒2/203；回归集均正确拒答 **0/17**、误拒0/43。拒答仍由BM25规则独立决定，不使用模型分数。

本机CPU、6个Torch线程的一次顺序运行中，开发集除首查外的平均检索耗时从26.8毫秒增至11.46秒，重排组P95为16.37秒；这是本轮观测，不是稳定性能基准。完整配置、权重修订、输入哈希、逐题排序、耗时与独立复核见 [实验归档](experiments/rerank-2026-10-26-run1/README.md)。该留出集已用于反馈，本轮属于回归评测，不是新的独立盲测。

## 题集、指标与历史验证

现有 **248道开发题**已重标为具体回答要点与最小充分证据：203道有答案、45道无答案，共320个要点、504段原文证据。3道原无答案题根据正文纠正，题干、ID和source未改；修订说明及哈希见 [标注说明](data/README.md)和 [manifest](data/eval/annotation_manifest.json)。证据长度中位数78.5字符，最长354字符。

`internal`为读正文出题（103道可答），`external`为只看标题出题（100道可答）。留出集重标后的62题含43道完整可答、17道无答案和2道待复核；待复核题不进入主指标和拒答分母。

开发集45道无答案题全部来自 `internal`（该来源共148题）；`external`共100题，全部可答。因此开发集的拒答结论只覆盖internal来源，尚未评估external来源的无答案拒答。题型中multi_block为16/248（6.5%，建议15%），cross_doc为5/248（2.0%，建议10%）；题型不均衡限制了对多块和跨文档问题的判断。

指标定义与限制：

- 前k块在同文档内取字符区间并集，每段必要证据的覆盖字符数须**严格超过证据长度的50%**；恰好50%不算。重复块不重复累计，中间空隙不计覆盖，同一要点的所有必要证据均须达标。
- 要点Recall@k先计算每题命中要点比例，再按题平均；全部要点命中率要求该题所有要点均命中。前缀MRR是前k块首次联合支持任一要点时的排名倒数，不要求支持全部要点。均只统计有答案题。
- 字符覆盖可能遗漏关键条件，不是语义充分性检查或回答正确率。标注经过AI辅助原文复核及机械校验，尚无独立人工验收。
- v2的标注、题型分母和判分均与旧版小节相交口径不同，新旧成绩不能直接比较。
- 默认 `final_k=5`，报告中的 @6～@10 与 @5 相同，不能据此判断前 10 个候选的召回能力。
- 248 道题已参与开发反馈；两种出题来源也不是训练/测试划分，均不能据此宣称独立泛化表现。
- 重排输入最多512 token，超长时截断；覆盖评分针对整个返回块，不证明模型读取了块中全部证据。

自动测试（2026-10-26）：本轮修正后完整套件 **458 passed in 15.36s**，默认配置仍为 `rerank.enabled=true`。模型相关用例显式关闭重排或使用替身，不加载预训练权重；CI仅安装 `[dev]` 并跑自动测试，绿灯不证明默认查询的语料、索引和本地模型已就绪。预训练模型的质量验证来自上述单独运行的对照实验。

## 复现评测与消融

先准备与标注匹配的语料和索引，再运行：

```powershell
.\.venv\Scripts\python.exe scripts/check_qrels.py data/eval/qrels.json
.\.venv\Scripts\python.exe scripts/run_rerank_experiment.py --out experiments/rerank-reproduction --threads 6
.\.venv\Scripts\python.exe scripts/check_rerank_experiment.py --path experiments/rerank-reproduction
.\.venv\Scripts\python.exe demo_ablation.py --index-dir data/index --out reports/ablation.json
```

对照实验的输出目录必须不存在，配置固定且忽略外部 `RAG__` 覆盖；需要与归档匹配的本地语料、索引、模型缓存和依赖。只跑新流程开发集时可用 `ragkit eval --config experiments/rerank-2026-10-26-run1/config.cross_encoder.json --qrels data/eval/qrels.json --out reports/eval.cross_encoder.json`；重现融合对照须改用 `config.fusion_only.json`，不能用当前默认流程代表历史配置。

`check_qrels.py`默认将建议配比偏差列为警告，格式或证据错误才返回非零；加 `--strict` 后警告也返回非零。当前题型配比超出建议容差，严格检查会失败；不能把普通模式通过理解为样本分布均衡。

`demo_ablation.py` 的六组为 baseline、alpha_09、alpha_05、rrf、bm25_only、dense_only，比较默认加权融合、α=0.9、α=0.5、等权 RRF 和两种单路，使用检索默认配置加各组覆盖项，并显式设置 `rerank.enabled=false`。六组不加载重排模型，不受应用默认启用设置影响；输出分别展示 fusion 与 model rerank 状态，并保存检索 config、rerank_config 和 scoring。旧组名 no_rerank 改名为 rrf；这里没有 cross-encoder 开关的质量对照。报告应随代码、题集、索引与有效配置一起解释；本次未重跑消融，不沿用旧数字断言某组件或参数最优。

消融表的Recall/MRR是全部定稿可答题的按题宏平均：当前分母为203，45道无答案题不计入。它不是internal或external分组成绩，例如全局Recall@1约0.379不能直接与上表的0.460或0.295比较；需使用同一统计范围。质量评测由显式命令运行，普通CI不覆盖约60.1分钟的这轮四块实验，也不证明默认模型链路可启动。

## 历史盲测结果（2026-10-23，2026-10-24重评）

原实验代码 `80b6aea`，两组均未使用真实 cross-encoder。2026-10-24先只看题干和原文重标62题，在提交 [`b63d485`](https://github.com/shenjingzhonggudie/nexus-rag/commit/b63d485) 冻结并推送答案后，才打开两份原检索报告，保留原检索顺序重评，未重跑模型。

重标后为43道完整可答、17道无答案、2道待复核。3道原无答案题有明确的限定回答，已记录更正理由；2道题分别存在原文内部冲突、默认值未写明的问题。主要指标只统计43道已定稿可答题：

| 配置 | 要点Recall@5 | 前缀MRR | 全部要点命中@5 | 无答案正确拒答 |
|---|---:|---:|---:|---:|
| BGE＋加权融合 | 0.913 | 0.8605 | 36/43（83.7%） | **0/17** |
| hashing＋等权 RRF | 0.855 | 0.7558 | 34/43（79.1%） | **0/17** |

- 每段必要证据须由前k块联合覆盖**严格超过50%**，恰好50%不算；同一要点的所有必要证据均须达标。将2道待复核题按未完整覆盖计入45题分母后，保守整题命中率为80.0%和75.6%。
- 旧报告没有最终回答正文，只能重评检索证据覆盖，不能据此报告回答正确率；仅首块就覆盖全部要点的比例为24/43（55.8%）和21/43（48.8%）。
- 新旧标注、分母和判分不同，不能直接比较；样本少、题型与开发集不同，且已用于开发反馈，这次重评不是新的独立盲测。

**两组对17道无答案题仍全部漏拒。** [重标、冻结、逐题覆盖与复现方法](experiments/holdout-evidence-v2/README.md)另存；[原始归档](experiments/holdout-v1/README.md)保持不变。

> **两套数字的关系**：原始归档 `holdout-v1/` 记录的是 2026-10-23 那次封存运行的**v1 口径**成绩
> （块与标注的小节区间相交即命中，42 条可回答，配置 A recall@5 **0.964**）；本节的表格是
> 2026-10-24 按 **v2 证据覆盖口径**重评的结果（43 条可回答，recall@5 **0.913**）。分母和命中
> 规则都不同，**两个数不能相互比较**，也不能据此认为重评导致成绩下降。

## 代码与文档

```text
文档 → loaders → chunking → embeddings → index / stores
问题 → BM25 + dense → 融合去重取top_k → 可选cross-encoder → 取final_k → 拒答 → 块原文与引用
题集 → 检索 → 回答要点的必要证据联合覆盖 → 分组指标
```

[模块契约](docs/PROJECT_LAYOUT.md) · [协作指南](AGENTS.md) · [项目概览](docs/SUMMARY.md) · [历史开发记录](docs/LEARNING_LOG.md) · [数据来源](data/SOURCES.md)
