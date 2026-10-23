# 独立留出集评测：rag-holdout v1.0.0

一轮**开发者不接触题目**的独立评测的完整记录：独立的出题 agent、独立的审核 agent、
预先冻结的配置，以及一次性的验收运行。

- 封存时间：2026-10-23 13:02（GMT+8）
- 验收运行：2026-10-23 13:20–13:30
- 被测代码：`80b6aea3da638057db4e531f05e5bedde14f956c`（验收期间工作区干净）
- 知识库：100 篇 / 984,360 码点（规范化后）
- 主集：**62 条**（42 可回答 + 20 同领域无答案），另有 4 条扩展题未纳入本轮

## 为什么做这一轮

开发集（`data/eval/qrels.json`，248 条）已经被用来观察系统行为、指导过修改，它上面的数字只能
算回归表现。这一轮的目的是拿一套**开发过程从未见过**的题目，测一次当前版本的真实水平。

隔离方式是**流程隔离**：出题与审核 agent 只拿到净化的输入包（语料、小节索引、格式契约），
拿不到项目源码、检索配置、拒答规则和历史分数。这是约定层面的隔离，不是文件权限隔离；
哈希能证明文件没被改动，但不能阻止被读取。

## 结果摘要

| | 配置 A：bge + 加权融合 α=0.7 | 配置 B：hashing + 等权 RRF |
|---|---|---|
| recall@1（可回答 42 条） | **0.738** | 0.667 |
| recall@3 | 0.952 | 0.905 |
| recall@5 | **0.964** | 0.929 |
| MRR | **0.893** | 0.831 |
| 误拒（可回答题） | 0 / 42 | 0 / 42 |
| **无答案正确拒答** | **0 / 20** | **0 / 20** |
| 冷启动 / 热启动 P50 | 31.2 s / 38.4 ms | 34 ms / 17.2 ms |

两个配置都在运行前预登记（见 `audit/freeze_check.md` 与 `audit/frozen_configs/`），
运行后未追加候选、未改阈值、未依据分数删题。

## 三个核心发现

**① 拒答在留出集上完全失效（0/20）**

20 条无答案题的 `match_score` 最低 **0.367**、最高 **1.000**，全部远高于阈值 `0.05`，
没有任何一条触发拒答。这与开发集上的表现形成直接对照：开发集的 48 条无答案题里，
18 条含语料外英文技术名（靠强信号规则命中），另外 30 条同领域困难负例**同样 0 拒答**。
留出集这 20 条是独立作者按"主题在语料里、但所问具体点缺失"构造的，**再次全部漏拒**。

> 结论：当前拒答能力约等于"只识别语料里完全没出现过的英文技术名"。
> 判断"证据是否足以回答"需要另一套机制，不是词覆盖率阈值能解决的。

**② 配置 A 全面优于配置 B，差距集中在跨文档题**

recall@5 +0.035、MRR +0.062。分类型看，差距几乎全部来自 `cross_doc`：
A 的 @5 是 0.700，B 只有 0.400。这与消融结论一致——字面哈希向量对"需要跨文档关联"的
查询帮助有限。

**③ 可回答题的证据充分性（人工子集 12 条，预登记分层抽样）**

| | 配置 A | 配置 B |
|---|---|---|
| 可回答题证据充分 | **8 / 8** | 7 / 8（h_0030 不足） |
| 无答案题返回"看似相关但答不了" | 4 / 4 | 4 / 4 |

该核对与区间命中**相互独立**：区间命中不等于证据够用。例如 h_0044、h_0062 区间命中且
证据充分，而 B 的 h_0030 区间未命中、证据也确实不足。

## 与开发集的数字不能直接比较

同一套代码在留出集上 recall@1 = 0.738，在开发集 `internal` 组上是 0.550。**这个差距主要不是
"变强了"，而是题型配比不同**：

| 类型 | 开发集 internal（n=100） | holdout（n=42） |
|---|---|---|
| `direct` | 39% | **69%** |
| `paraphrase` | **41%** | 12% |
| `multi_block` | 15% | 7% |
| `cross_doc` | 5% | 12% |

`direct` 题直接用文档术语提问，命中率天然高于 `paraphrase`（换说法）。留出集以 `direct` 为主，
因此整体 recall 更高。**两个数字各自在其配比下有效，混在一起比会得出错误结论。**

## 题量流转（候选 → 封存）

```
候选主集 63  ─┬─ 通过 61 ─┐
              ├─ 修订  1 ─┤→ 封存主集 62
              └─ 排除  1 ─┘   （h_0038 与开发题 q_0199 语义近重复）
候选扩展   4  ── 通过 4 ───→ sealed/challenges.jsonl（未纳入本轮评测）
候选待定   2  ── 待定 2 ───→ 未入集
                   合计 69 条，与 audit/review.jsonl 的 69 条逐条对应，无遗漏
```

`sealed/metadata.jsonl` 有 **66 条**（62 主集 + 4 扩展题），用 `set` 字段区分，不是重复或错误。

## 目录结构

```
experiments/holdout-v1/
├── PROTOCOL.md                  原四阶段流程指令（出题/审核/验收的分工与约束）
├── ARCHIVE_MANIFEST.json        本归档 42 个文件的 SHA-256 与排除清单
├── input/                       阶段一：净化的输入包（开发者准备）
│   ├── FORMAT.md                标注格式与评估契约
│   ├── sections.jsonl           477 个小节的标题与区间
│   ├── old_queries.jsonl        248 条开发题题面（仅供审核者去重）
│   └── corpus_manifest.json     语料哈希、导出时间、代码版本
├── candidate/                   阶段二：独立出题 agent 的产出
│   ├── qrels.candidate.json     63 条候选题（h_ 前缀）
│   ├── evidence.jsonl           逐题答案要点、引文、区间；无答案题的检索核验
│   ├── pending.jsonl            2 条无法确认的题及原因
│   ├── challenges.jsonl         4 条扩展行为题
│   ├── build_problems.txt       编译期自检结果（"无问题"）
│   └── tools/                   出题与自检脚本、小节索引、区间核验记录
├── audit/                       阶段三/四：独立审核与验收
│   ├── review.jsonl             69 条逐题结论（通过 65 / 修订 1 / 排除 1 / 待定 2）
│   ├── freeze_check.md          冻结状态核查 + 两个配置的预登记（先于运行写入）
│   ├── frozen_configs/          配置 A / B 的固定 YAML
│   ├── eval.configA.bge.weighted.json   配置 A 逐题结果（42 条可回答，含 20 条无答案记录）
│   ├── eval.configB.hashing.rrf.json    配置 B 逐题结果
│   ├── ACCEPTANCE_REPORT.md     验收报告（本文件结论的原始出处）
│   ├── human_subset_evidence.json       12 条人工子集的 top-5 返回证据原文
│   ├── answerable_intervals.txt          可回答题：标注区间 + 对应原文
│   ├── noanswer_search.txt / noanswer_compact.txt   无答案题的全库检索记录
│   ├── mech_report.json         机械校验（区间合法性、引用子串等）
│   └── tools/                   密封、核对、机械校验脚本
└── sealed/                      阶段三：封存产物
    ├── qrels.test.json          **最终评测标注（62 条）**
    ├── metadata.jsonl           66 条旁表（62 主集 + 4 扩展），含 family_id / 类别
    ├── challenges.jsonl         4 条扩展题（未纳入本轮 recall/拒答统计）
    └── manifest.json            题量、类型分布、文件哈希、评测口径、修订日志
```

## 归档取舍

**排除**（12 个文件，约 1.68 MB）：

| 文件 | 原因 |
|---|---|
| `input/corpus.jsonl` | 100 篇完整第三方原文（1.36 MB）。仓库约定不入库，可由 `scripts/fetch_docs.py` 重新拉取 |
| `candidate/tools/dump_*.txt`（5 个） | 出题者为阅读语料抽出的全文转储，不含额外信息 |
| `candidate/tools/__pycache__/`（6 个） | 字节码缓存 |

**保留但需说明**：`audit/noanswer_search.txt`、`audit/noanswer_compact.txt`、
`audit/answerable_intervals.txt`、`candidate/tools/verify_*.txt` 含第三方原文的**片段摘录**。
保留的原因是它们是审核结论的直接依据（"为什么判定全库无答案"、"这条题的支撑原文是什么"），
与"完整语料转储"性质不同。

## 核对结果（归档时执行）

| 项 | 结果 |
|---|---|
| `sealed/manifest.json` 记录的 7 个文件哈希 | **7 / 7 一致** |
| 归档 42 个文件的源→归档哈希 | **42 / 42 一致** |
| 主集题量 | 62 条，与 `counts.main` 一致 |
| 主集类型分布 | direct 29 / paraphrase 5 / multi_block 3 / cross_doc 5 / no_answer 20，与 `main_by_type` 逐项一致 |
| id 唯一性与前缀 | 62 条 id 唯一，全部 `h_` 前缀 |
| review 覆盖 | 69 条结论 = 63 候选 + 4 扩展 + 2 待定，逐条对应，无遗漏 |
| 报告数字 vs eval 原始输出 | 配置 A `0.738 / 0.952 / 0.964 / 0.893`、配置 B `0.667 / 0.905 / 0.929 / 0.831`，**逐项一致** |
| 拒答数字 | 两配置 `accuracy = 0.000`（0/20），与报告一致 |

**未发现矛盾**。两处容易误读的地方已在上面写明：`metadata.jsonl` 66 条 vs 主集 62 条、
以及 holdout 与开发集的 recall 不可直接比较。

## 已知局限

- **仅覆盖检索层**：系统当前是抽取式（`llm.provider=none`），本轮没有评测生成模型的
  忠实性、纠错或部分回答能力；`0/20` 的含义是"未触发拒答"，不是"生成层答错了"。
- **4 条扩展题未运行**：`challenges.jsonl` 的格式不在 `eval --qrels` 入口支持范围内。
- **2 条待定题未入集**：作者无法确认语料是否真的无答案，按规则不进入主集。
- **配置 A 首跑失败并重试**：首次运行因 HF hub 联网校验模型（代理 502）失败，置
  `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` 后成功。属运行环境修复，未查看成绩调参。
- **样本量**：42 条可回答题，recall@1 的标准误约 0.07，配置间 0.07 的差处在噪声边缘；
  recall@5 的差距（0.964 vs 0.929）更可信。
- **流程隔离非权限隔离**：各 agent 共享全盘读取权限，封存靠约定与哈希核对维持。

## 复现

```powershell
cd C:\Users\王佳浩\Desktop\项目
$env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"

# 配置 A（bge + 加权融合）
.\.venv\Scripts\ragkit.exe eval \
  --qrels experiments\holdout-v1\sealed\qrels.test.json \
  --config experiments\holdout-v1\audit\frozen_configs\configA.bge.weighted.yaml \
  --out reports\holdout-A.json

# 配置 B（hashing + 等权 RRF）
.\.venv\Scripts\ragkit.exe eval \
  --qrels experiments\holdout-v1\sealed\qrels.test.json \
  --config experiments\holdout-v1\audit\frozen_configs\configB.hashing.rrf.yaml \
  --out reports\holdout-B.json
```

需要先有索引（`ragkit build`）与 `data/raw` 语料；`input/corpus.jsonl` 已排除，
可用 `scripts/fetch_docs.py` 重新拉取，并用 `input/corpus_manifest.json` 的哈希核对是否一致。

## 使用约束（重要）

**本测试集自验收起已进入开发反馈循环。** 本轮暴露的失败（无答案 0/20、配置 B 的
`cross_doc` 缺口）如果用于修改系统，则此后在本集上的任何成绩只能作为**回归表现**解读，
不能再当作"未见数据上的能力证明"。下一轮独立结论需要重新构造、未被接触过的测试题。

封存后如发现标注错误，应在 `sealed/manifest.json` 的 `revision_log` 中记录并递增版本号，
不得静默修改答案。当前 `revision_log` 有 2 条（h_0022 修订、h_0038 排除）。
