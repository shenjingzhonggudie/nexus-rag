# data/ 目录说明

## 结构

```
data/
├── raw/                        # 语料正文（第三方公开文档，gitignore，由脚本拉取）
├── eval/
│   ├── qrels.json                     # 评测标注（218 条，人工筛选后提交）
│   ├── qrels.example.json             # 格式示例（五类各一条）
│   ├── independent_titles_batch2.json # 外部出题的输入（150 个标题，只有 doc/section，没有 query）
│   └── external_queries_batch2.json   # 外部产出（150 条：103 条有效 + 47 条 skip）
├── index/                      # 建库产物（gitignore，可重建）
└── SOURCES.md                  # 数据来源与许可证（fetch 时生成，要提交）
```

> **为什么不提交 `raw/`**：正文是第三方文档，再分发受各自许可证约束；同时几十
> 万字的正文会把仓库撑大。所以仓库里只放**下载脚本 + 来源清单**，谁需要谁拉。
> 来源、仓库、许可证都记在 `SOURCES.md` 里。

## 标注格式（不绑切分）

`qrels.json` 的每一条：

```json
{
  "query": "为什么组合索引要把选择性高的列放左边？",
  "type": "paraphrase",
  "answers": [
    {"doc": "mysql/组合索引.md", "section": "最左前缀原则", "start": 1234, "end": 2345}
  ]
}
```

- `doc`：相对 `data/raw/` 的路径，与 `Chunk.doc_id` 同口径；
- `section`：小节标题，**仅供人工核对与报告展示**，不参与匹配；
- `start` / `end`：小节在 `normalize_text(文档原文)` 中的字符区间（左闭右开）；
- `answers` 为空列表 → 无答案 query（测拒答）；
- `source`：题目来源，`internal`（读正文出题，答案保证可被该节回答）或
  `external`（只看标题出题，更接近真实用户问法）。`ragkit eval` 会按它分组打印。

**为什么不用 chunk_id**：chunk_id 是切分产物，换 `chunk_size` 或换分块策略
（`fixed` / `heading` / 未来的 `recursive`）就全部失效，标注得重做。字符区间
是文档的固有属性，评测时只判断「召回的块与答案区间是否重叠」，所以**换切分
不用重标**。

## 从零到有标注：完整流程

```powershell
# 1. 拉语料（需联网；来源与许可证见 data/SOURCES.md）
.\.venv\Scripts\python.exe scripts/fetch_docs.py --list   # 先看清单
.\.venv\Scripts\python.exe scripts/fetch_docs.py          # 下载

# 2. 列出小节 + 字符区间（人工选题用）
.\.venv\Scripts\python.exe scripts/section_index.py

# 3. 为某个小节生成"出题 prompt"，贴给任意 LLM
.\.venv\Scripts\python.exe scripts/gen_queries.py --prompt 3 --type paraphrase

# 4. 人工筛选（关键，不能省）：
#    - 删掉照抄原文术语的题（direct 占 30% 就够）
#    - 删掉答案不唯一、有歧义的题
#    - 把保留的题连同 doc/section/start/end 填进 data/eval/qrels.json

# 5. 质检（格式、区间合法性、小节对齐、类型配比）
.\.venv\Scripts\python.exe scripts/check_qrels.py data/eval/qrels.json

# 6. 建库 + 评测
.\.venv\Scripts\ragkit.exe build
.\.venv\Scripts\ragkit.exe eval
```

## 当前构成（218 条）

| 来源 | 数量 | 说明 |
|---|---|---|
| `internal` | 100 | 读过正文出题，答案保证能被该节回答 |
| `external` | 100 | 只给标题、不看正文出题（提交 150 条，skip 47 条 → 103 条有效；剔除 3 条区间过长的，留 100 条） |
| `no_answer` | 18 | 语料外主题 |

三点说明：

- **有答案部分的比例是 100 : 100（精确 50:50）**；
- **`external` 只含 `direct` / `paraphrase`**——“只看标题”写不出 `multi_block`（答案分散在
  2~3 节）和 `cross_doc`（跨文档对比），这两类仍全部来自内部组（16 + 5 条）。
- **早期一批 40 个标题的试点已移除**：当时 32 条有效、剔掉 5 条超纲后留 27 条。样本太小
  （27 条时 external recall@1 = 0.333，扩到 100 条后为 0.390），已由当前
  100 条**整体替换**（不是追加），原始文件随之删除。演进过程见 `docs/LEARNING_LOG.md`。

## 复核日志（`review_log.jsonl`）

`data/eval/review_log.jsonl` **每个样本保留一行 JSON**，以 `sample_id` 为唯一键。
补充或修正复核结论时更新该样本所在行，保留最新结论与完整建议，并按样本编号排序。
格式见 `data/eval/review_log.example.jsonl`。

**每个样本都要有明确结论**：通过简记，发现问题详记；没有日志表示未复核，不能当作通过。
不在本次复核范围内的样本（例如只检查答案匹配时的 `no_answer`）也要登记为 `跳过`，说明原因，不能冒充通过。

| 字段 | 含义 |
|---|---|
| `sample_id` | 稳定样本 ID（`q_0042`）。**改了 query 或答案也保留同一个 ID**——它标识"这道题"，不是"这版标注" |
| `query` | 复核时的题干（写进日志便于自解释，不用回查 qrels） |
| `original_label` | 复核前的答案绑定：`[{doc, section, start, end}]`；通过简记时也是支持答案的原文位置 |
| `issue` | 发现的问题（一句话说清"为什么不对"）；通过或跳过时为 `""` |
| `decision` | `通过` / `修正答案绑定` / `删除该条` / `待定` / `跳过` |
| `corrected_label` | 修正后的答案绑定；通过、删除、待定或跳过时为 `[]` |
| `evidence` | 问题详记时**粘贴实际支持回答的原文句子**（不是转述）；确实没有支持内容时为 `""`。通过简记允许为 `""`，用 `original_label` 定位原文 |
| `rationale` | 通过时简记匹配依据；问题详记时说明引文回应了哪些具体要求；待定时写清**缺少什么证据、需要谁进一步确认**；跳过时说明范围和原因 |
| `reviewer` | `{name, saw_fulltext}`——模型名或 `human`；仅确实读完整篇文档时 `saw_fulltext=true`，只读片段或完整相关小节仍为 `false` |
| `data_version` | `{qrels_commit, doc_sha256_prefix}`——标注的 Git commit + 原文内容哈希前 8 位 |
| `reviewed_at` | ISO 8601 时间 |

**为什么记这么细**：复核的价值不在"判了对错"，而在"以后能复查这个判断的依据"。
只有 `OK / ✗` 的日志，三个月后没人知道当时为什么这么判。

**约定**：一条样本一行，`sample_id` 不重复；本轮 218 个样本对应 218 行记录。
统计前校验行数、唯一 ID 数及样本覆盖范围一致；更新建议合并到原记录中，`reviewed_at` 记最近复核时间。

## 类型配比（建议）

| 类型 | 含义 | 建议占比 |
|---|---|---|
| `direct` | 直接用术语问 | 30% |
| `paraphrase` | 换说法、不照抄术语 | 30% |
| `multi_block` | 答案分散在 2~3 个小节 | 15% |
| `cross_doc` | 需要跨文档对比 | 10% |
| `no_answer` | 语料里没有答案（测拒答） | 15% |

`check_qrels.py` 会把实际配比和建议配比并排打印，偏离超过 8 个百分点会标出来。

## 规模参考

- 文档 **30~100 篇**，总量 **50 万~200 万字**：太少了测不出区分度，太多了
  建库和评测都变慢；
- 要有**相似主题的干扰文档**（比如 MySQL 索引 vs Redis 持久化），否则检索
  只要认出领域就能得分，测不出真正的区分能力；
- 长短不一、结构不一（有的带 `##` 层级、有的是纯段落），这样才能考验切分。

## 防过拟合：盲测集

调参（`fusion_alpha`、`top_k`、`chunk_size`、`refuse_threshold`）只看
**80% 的题**，剩下 **20% 留作盲测**，最终数字在盲测集上报告。样本只有几十条时
这一点尤其重要——否则调出来的"最优参数"只是在拟合噪声。

建议在 qrels 里给每条加一个 `split` 字段（`dev` / `test`），或将两个集合拆成
`qrels.dev.json` 与 `qrels.test.json` 分开跑。
