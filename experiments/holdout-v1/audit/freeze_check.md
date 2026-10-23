# 冻结状态核查报告（验收前置检查）

- 核查时间：2026-10-23 13:05–13:20（GMT+8）
- 核查性质：只读核对 + 补录哈希/依赖清单。**未运行封存测试集，未查看任何测试成绩。**
- 封存位置：`C:/Users/王佳浩/codex/2026-10-23/new-chat/outputs/rag-holdout/`
- 项目位置：`C:/Users/王佳浩/Desktop/项目`

---

## 一、已完整记录的冻结项（核对通过）

### 1. 项目代码 commit 与工作区状态
- HEAD：`80b6aea3da638057db4e531f05e5bedde14f956c`
  （2026-10-23T12:03:47+08:00，"test(eval): add 30 hard negatives; refusal accuracy drops 100% -> 37.5%"）
- 分支：master；**工作区干净，无未提交修改**（`git status` 零输出）。

### 2. 封存题集与标签（哈希逐一核对，全部 OK）
对照 `sealed/manifest.json` 记录值重新计算 SHA-256：

| 文件 | 核对结果 |
|---|---|
| sealed/qrels.test.json | OK（8e3646a2…） |
| sealed/metadata.jsonl | OK（bdb4ea34…） |
| sealed/challenges.jsonl | OK（c1407a2e…） |
| input/corpus.jsonl | OK（30a94bb2…） |
| input/sections.jsonl | OK（c62b86cd…） |
| input/old_queries.jsonl | OK（b520cedc…） |
| input/corpus_manifest.json | OK（e1df720b…） |

题集版本 1.0.0，封存于 2026-10-23T13:02:23+08:00；逐题条数 62 与 manifest 一致
（direct 29 / no_answer 20 / cross_doc 5 / paraphrase 5 / multi_block 3；另有 challenges 4、pending 2、excluded 1）。
修订记录（revision_log：h_0022 改型、h_0038 排除）已在 manifest 内保留。

### 3. 预定报告口径（manifest.eval_protocol，封存时已固定）
- 可回答题误拒率：可回答题 n=42 中整体拒答比例；
- 无答案拒答：按类别报正确拒答数/总数（含困难无答案子类，如 h_0013/h_0035/h_0053/h_0068）；
- 检索：recall@5 与 MRR，块级命中 = 与任一标注区间同文档且重叠，k=5；
- 明示 caveat：区间命中不得解释为最终回答正确率，最终回答正确率需人工核对证据充分性；
- 人工核对子集（验收前固定，12 条）：h_0003, h_0011, h_0013, h_0021, h_0030, h_0032,
  h_0044, h_0046, h_0053, h_0059, h_0062, h_0068（含 3 条困难无答案）。

### 4. 生成模型
- `llm.provider = none`：**未接入生成模型**。无提示词、无随机采样参数需记录。
- 与验收报告第 5 条约束一致：本次只评测抽取式/检索层，不声称已测生成忠实性。

---

## 二、本轮补录（此前无预记录，现补齐；只读计算）

### 1. 知识库规范化文本与索引文件哈希（SHA-256，2026-10-23 补录）
两套索引的规范化分块文本完全一致（chunks/ids/metadata 三件哈希相同），仅向量与 manifest 不同：

| 文件 | SHA-256 | 备注 |
|---|---|---|
| data/index/chunks.jsonl | c372aba06886d2fa875abfec8663e164585a64f0af929fef02e50e7fe7f997a0 | bge 索引，规范化分块文本 |
| data/index/ids.json | 97959a964b3f4e31311f7b7767b5e0f68972fbc56055f5908da7b20b0efeac02 | |
| data/index/metadata.json | 27693c8ee5f00bc7f322b9878d6cc729b12bd41db36705ec2ab1f9a7d19975ef | |
| data/index/manifest.json | dfc820befb6e48b5f15e1f6b18683ca84e45dd888872a53ed180a731ea931b4b | provider=bge, dim=512, count=1553 |
| data/index/vectors.npy | 80b09e61aad62308f4e865b0699f577efded2f0a51d0d7dee8f54e6cfb55f23f | bge 向量 |
| data/index.hashing/chunks.jsonl | c372aba0…（与上相同） | hashing 索引，同一份分块 |
| data/index.hashing/ids.json | 97959a96…（与上相同） | |
| data/index.hashing/metadata.json | 27693c8e…（与上相同） | |
| data/index.hashing/manifest.json | db629e4cb5e4dbc909890f2f9ae8be43c55ebf9c3ece0730fb115e5e82391de8 | provider=hashing, dim=512, count=1553 |
| data/index.hashing/vectors.npy | 3acab22ce434753f3f822cd1a9216d4a289736d94ff7c9cf1d2dc2538244bf05 | hashing 向量 |

- 两索引构建时间：hashing 2026-10-22T11:42:50，bge 2026-10-22T11:46:24（均早于 HEAD commit）。
- 语料源头已由封存 manifest 锁定（input/corpus.jsonl 哈希核对 OK）；`data/raw`、`data/index*`、`reports` 均为 gitignore 的可再生产物。

### 2. embedding 模型标识
- 名称：**BAAI/bge-small-zh-v1.5**（index manifest 自述；HF 缓存快照修订号
  `7999e1d3359715c523056ef9478215996d62a620`）。
- 向量维度 512；索引块数 1553。

### 3. 运行环境与依赖版本（venv freeze，2026-10-23 补录）
- OS：Windows（win32）；venv Python：3.12.10
- 项目：ragkit 1.0.0（`ragkit --version`）
- 关键依赖：numpy==2.5.4, pydantic==2.13.5, PyYAML==6.0.3, jieba==0.42.1,
  sentence-transformers==6.1.0, torch==2.14.1, transformers==5.20.2, tokenizers==0.23.3,
  huggingface_hub==1.33.0, safetensors==0.8.0, pytest==9.1.1, scikit-learn==1.9.1, scipy==1.18.1
- 已知瑕疵：`pip list` 显示 ragkit==0.0.1（editable 安装元数据未刷新，实际代码版本 1.0.0）。

---

## 三、缺项清单（**阻塞项：须在首次 eval 前补齐，不得参考测试成绩决策**）

### 缺项 1：最终有效配置未做冻结声明（唯一阻塞项）
现存配置存在三处未定/互相矛盾，且无任何文档或历史会话声明 holdout 验收用哪一套：

1. **embedding provider**：`configs/default.yaml` 写 `provider: hashing`（且 index_dir=data/index），
   但 `data/index/manifest.json` 自述该索引为 **bge** 构建。两套索引并存（第 28 轮日志明确列为"尚未解决"）。
2. **rerank_enabled**：`configs/default.yaml` 写 `false`（注释仍是第 27 轮前的旧口径
   "dense 余弦精排负贡献"），而 `config.py` 代码默认值为 `True`（第 28 轮已把 rerank 重定义为
   加权排名融合并翻转默认）。
3. **eval 报告不含配置快照**：`reports/eval.json`（开发集报告，2026-10-23T11:59 生成）未记录
   所用配置，事后无法反推开发结论对应的参数组合。

**需在运行前书面固定**（写入本文件或单独 freeze 文档）：provider（bge 或 hashing 及对应 index_dir）、
rerank_enabled、fusion_alpha、refuse_threshold、top_k/final_k，以及是否有 `RAG__*` 环境变量覆盖
（当前 shell 已确认无覆盖）。

### 缺项 2：非阻塞备注
- 检索代码在索引构建之后有改动（0af51af，2026-10-23 10:20，仅改拒答打分 key_term_coverage 的
  停用词过滤，不影响 chunks/BM25/向量）；如最终配置涉及重建索引需另行记录。
- 若验收时比较两个固定配置（如 bge+加权融合 与 hashing+RRF），须在首次运行前把两者全部列死，
  运行后不得追加候选。

---

## 四、结论
- 封存题集、标签、口径：**冻结完整，可进入验收**。
- 代码状态：**干净，commit 已固定**。
- 配置冻结：缺项 1 已由用户于首次运行前书面固定（见下），阻塞解除。

---

## 五、验收配置预登记（2026-10-23，首次运行前固定，运行后不得追加候选）

用户决定：**两个固定配置都跑**，作为同基线比较。以下两配置在首次 eval 前登记，此后不得
再增加候选、不得改阈值、不得依据分数删题。当前 shell 已确认无 `RAG__*` 环境变量覆盖。

### 配置 A：bge + 加权排名融合（`audit/frozen_configs/configA.bge.weighted.yaml`）
- embedding: provider=bge, model_name=BAAI/bge-small-zh-v1.5, dim=512（索引 data/index，manifest 自述一致）
- retrieval: top_k=20, final_k=5, rerank_enabled=true（加权排名融合）, fusion_alpha=0.7,
  sparse_enabled=true, dense_enabled=true, refuse_threshold=0.05
- chunking: heading / 300 / 50；llm: none（抽取式）

### 配置 B：hashing + 等权 RRF（`audit/frozen_configs/configB.hashing.rrf.yaml`）
- embedding: provider=hashing, dim=512（索引 data/index.hashing）
- retrieval: top_k=20, final_k=5, rerank_enabled=false（等权 RRF）, fusion_alpha=0.7,
  sparse_enabled=true, dense_enabled=true, refuse_threshold=0.05
- chunking: heading / 300 / 50；llm: none

### 运行命令（qrels=封存题集，报告落 audit，不覆盖原开发报告）
```
ragkit eval --config audit/frozen_configs/configA.bge.weighted.yaml \
  --qrels <holdout>/sealed/qrels.test.json --out audit/eval.configA.bge.weighted.json
ragkit eval --config audit/frozen_configs/configB.hashing.rrf.yaml \
  --qrels <holdout>/sealed/qrels.test.json --out audit/eval.configB.hashing.rrf.json
```

