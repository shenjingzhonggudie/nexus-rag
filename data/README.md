# 数据与评测标注

## 文件

| 路径 | 内容 |
|---|---|
| `raw/` | 第三方文档正文，未跟踪；来源见 [SOURCES.md](SOURCES.md) |
| `eval/qrels.json` | 现有 248 道开发题及答案区间 |
| `eval/qrels.example.json` | 标注格式示例 |
| `eval/review_log.jsonl` | 样本复核记录，格式见 `review_log.example.jsonl` |
| `eval/independent_titles_batch2.json` | 外部出题使用的标题资料 |
| `eval/external_queries_batch2.json` | 外部出题候选与 skip 记录 |
| `index*/` | 本地索引产物，未跟踪，可由匹配的语料与配置重建 |

`raw/` 正文按各来源许可证使用。下载脚本访问上游文档，重拉可能改变内容和字符坐标，不能保证复现既有语料快照。

## 标注格式

下面仅展示字段格式，示例区间不对应现有文档：

```json
{
  "id": "q_example",
  "query": "示例问题",
  "type": "paraphrase",
  "source": "internal",
  "answers": [
    {"doc": "example.md", "section": "示例小节", "start": 10, "end": 100}
  ]
}
```

- `id`：稳定样本标识，用于关联复核日志；加载器允许缺省，新题应填写唯一 ID。
- `doc`：相对语料根目录的路径，与 `Chunk.doc_id` 一致。
- `section`：供人工核对的小节标题，不参与命中计算。
- `start/end`：`normalize_text(load_file(path).text)` 中的字符区间，左闭右开。`load_file` 会处理 front matter、注释等，不能直接用原始文件字符坐标代替。
- `type`：`direct`、`paraphrase`、`multi_block`、`cross_doc` 或 `no_answer`。
- `answers=[]` 表示无答案题，类型应为 `no_answer`。加载器以答案是否为空判定有无答案，`check_qrels.py` 另检查题型一致性。
- `source`：出题来源。`internal` 表示参考正文出题，`external` 表示只参考标题出题；缺省为 `internal`。它不保证标注正确，也不表示 dev/test 划分。

答案以文档区间标注，不绑定 chunk_id。在规范化文档内容保持不变时，更换分块参数不需要重新定位答案；文档、加载器清理规则或规范化规则变化后，须重新校验区间。

## 当前开发集

2026-10-23 核对 `qrels.json`：

| 来源 | 有答案 | 无答案 | 合计 |
|---|---:|---:|---:|
| `internal` | 100 | 48 | 148 |
| `external` | 100 | 0 | 100 |
| 合计 | 200 | 48 | 248 |

题型为 direct 91、paraphrase 88、multi_block 16、cross_doc 5、no_answer 48。外部组现有题型仅 direct/paraphrase；两组题型构成不同，分数差异不能全部归因于提问措辞。

当前实测和指标定义统一见 [项目 README](../README.md#当前实测)。题集结构检查通过，只说明格式和区间等检查未报错，不证明答案充分性或无答案标签已逐题成立。

## 准备数据与运行

在仓库根目录执行：

```powershell
# 下载公开文档，需要联网；先查看来源清单
.\.venv\Scripts\python.exe scripts/fetch_docs.py --list
.\.venv\Scripts\python.exe scripts/fetch_docs.py

# 浏览小节候选；输出偏移不能直接用作正式标注
.\.venv\Scripts\python.exe scripts/section_index.py

# 为候选小节生成出题提示
.\.venv\Scripts\python.exe scripts/gen_queries.py --prompt 3 --type paraphrase

# 校验题集后，使用与语料匹配的配置建库和评测
.\.venv\Scripts\python.exe scripts/check_qrels.py data/eval/qrels.json
.\.venv\Scripts\ragkit.exe build
.\.venv\Scripts\ragkit.exe eval
```

`section_index.py`、`gen_queries.py` 和 `build_skeleton.py` 目前直接对 `read_text()` 的结果做规范化，未经过 `load_file` 清洗。它们仅供浏览和生成候选，输出偏移不能直接写入 qrels。正式标注须在 `normalize_text(load_file(path).text)` 上重新定位区间，再运行 `check_qrels.py`；结构检查通过也不能代替原文证据核验。

建库默认写 `data/index` 并使用 hashing。需要保留已有 BGE 或实验索引时，先用 YAML 指定另一个 `index_dir`，并对 build/eval 传入同一配置。

出题后应核对题干的对象、条件和范围，确认全部回答要点都有证据；无答案题要检查全库相关文档及可能的跨段推导，不能仅凭关键词未命中下结论。`check_qrels.py` 检查格式、重复 query、文档存在、区间范围与小节相交，并打印题型配比；配比建议不构成标签质量保证。

## 复核日志

`review_log.jsonl` 每个 `sample_id` 保留一条记录，更新时保留核验依据。字段如下：

| 字段 | 含义 |
|---|---|
| `sample_id` / `query` | 样本标识及复核时题干 |
| `original_label` / `corrected_label` | 原答案区间与修正区间 |
| `decision` | 通过、修正答案绑定、删除该条、待定或跳过 |
| `issue` / `rationale` | 问题说明、核验理由及范围 |
| `evidence` | 实际支持判断的原文；通过简记允许为空，可通过原标签定位 |
| `reviewer` | 复核者及 `saw_fulltext`；只有实际读完整篇时才为 true |
| `data_version` | 题集 commit、文档哈希前缀 |
| `reviewed_at` | 最近复核时间 |

2026-10-23 核对：日志有 218 行、218 个唯一 ID，覆盖当前题集的 218 道题；其余 30 道没有对应日志。记录结论为通过 190、修正答案绑定 9、跳过 18、待定 1。这是记录状态统计，本轮未重新审查逐题证据，也未确认所有修正建议已应用，不能据此称全题均已复核通过。

## 开发集与独立验收

现有 248 道题已用于观察行为和开发调整，全部按开发集使用。现在追加 `split` 字段或重新抽取 20% 不能恢复未见测试的独立性；加载器当前也不使用 `split`。

独立验收须在看成绩前固定新题、标注、代码、语料、索引和有效配置，并记录测试反馈是否参与后续修改。[历史实验归档](../experiments/holdout-v1/README.md)保留既有流程与记录，本轮未复核其标签或成绩。若某题集反馈已用于修改系统，后续分数应作为该集上的回归结果。
