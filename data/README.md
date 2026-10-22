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
  2~3 节）和 `cross_doc`（跨文档对比），这两类仍全部来自内部组（16 + 6 条）。
- **早期一批 40 个标题的试点已移除**：当时 32 条有效、剔掉 5 条超纲后留 27 条。样本太小
  （27 条时 external recall@1 = 0.333，扩到 100 条后为 0.350），已由当前
  100 条**整体替换**（不是追加），原始文件随之删除。演进过程见 `docs/LEARNING_LOG.md`。

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
