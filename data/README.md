# 数据与评测标注

## 文件

| 路径 | 内容 |
|---|---|
| `raw/` | 第三方文档正文，未跟踪；来源见 [SOURCES.md](SOURCES.md) |
| `eval/qrels.json` | 248道开发题，v2回答要点与最小充分证据 |
| `eval/qrels.example.json` | 标注格式示例 |
| `eval/evidence_review.jsonl` | 本轮248题的旧标签、修订理由与复核范围 |
| `eval/annotation_manifest.json` | 标注版本、题集与规范化正文哈希、判分定义 |
| `eval/review_log.jsonl` | v1历史复核记录，格式见 `review_log.example.jsonl` |
| `eval/independent_titles_batch2.json` | 外部出题使用的标题资料 |
| `eval/external_queries_batch2.json` | 外部出题候选与 skip 记录 |
| `index*/` | 本地索引产物，未跟踪，可由匹配的语料与配置重建 |

`raw/` 正文按各来源许可证使用。下载脚本访问上游文档，重拉可能改变内容和字符坐标，不能保证复现既有语料快照。

## 标注格式

v2把每个问题拆成必要回答要点，每个要点绑定足以支持该要点的精确原文。下面是虚构示例，坐标相对示例正文，不对应现有语料：

```json
{
  "id": "q_example",
  "query": "示例问题",
  "type": "paraphrase",
  "source": "internal",
  "annotation_version": 2,
  "annotation_status": "complete",
  "answers": [
    {
      "point": "查询只取需要的列。",
      "evidence": [
        {"doc": "example.md", "section": "查询", "start": 0, "end": 9, "quote": "查询只取需要的列。"}
      ]
    }
  ]
}
```

- `id`：稳定样本标识，用于关联复核日志；加载器允许缺省，新题应填写唯一 ID。
- `point`：具体且可核验的必要回答要点，不以标题或问题复述代替答案。
- `evidence`：共同支持该要点的必要原文片段，全部都需命中。仅保留充分表达结论和必要条件的文字；不把整节、整个示例或额外背景当作默认答案。不支持把等价证据作为OR备选，当前标注也不保证穷尽全库等价表述。
- `doc`：相对语料根目录的路径，与 `Chunk.doc_id` 一致。
- `section`：供人工核对的小节标题，不参与命中计算。
- `start/end`：`normalize_text(load_file(path).text)` 中的字符区间，左闭右开。`load_file` 会处理 front matter、注释等，不能直接用原始文件字符坐标代替。
- `quote`：与规范化正文的 `[start:end]` 完全一致，长度必须等于 `end-start`。
- `type`：`direct`、`paraphrase`、`multi_block`、`cross_doc` 或 `no_answer`。
- v2无答案题须显式标为 `type=no_answer`、`answers=[]` 并填写 `unanswerable_reason`。有答案题不能因漏标证据而被静默视为无答案；待定题用 `annotation_status=needs_review`，不进入指标分母。
- `retained_no_answer` 表示保留既有无答案标签，补充缺失信息说明；不表示完成了独立的全库无答案审核。
- `source`：出题来源。`internal` 表示参考正文出题，`external` 表示只参考标题出题；缺省为 `internal`。它不保证标注正确，也不表示 dev/test 划分。

答案以文档区间标注，不绑定 chunk_id。在规范化文档内容保持不变时，更换分块参数不需要重新定位答案；文档、加载器清理规则或规范化规则变化后，须重新校验区间。

`.gitattributes`固定新版qrels为LF换行，保证Windows与其他系统检出后的字节哈希一致。改标注时须同步更新manifest和复核记录。

## v2判分

1. 取前k个检索块，按文档对字符区间求并集；重复和重叠不重复累计，中间未检索的空隙不计覆盖。
2. 每段必要证据的覆盖率为 `并集覆盖该证据的字符数 / 该证据字符数`，须**严格大于50%**；恰好50%不算。
3. 一个要点的所有必要证据均达标，该要点才命中。Recall@k按题计算要点覆盖比例后平均；`complete_at[k]`统计全部要点均命中的题目比例。
4. MRR取首次命中任一要点的前缀排名倒数；它不要求整题要点全部命中。无答案题只进入拒答指标。

这是字符覆盖代理指标，超过50%仍可能遗漏否定词或关键条件，不能等同语义充分性或回答正确率。v1旧格式保留原有任意小节相交判分，不能与v2混合汇总或直接比较成绩。

## 当前开发集

2026-10-24重标现有题目，保留248道题的ID、题干和source：

| 来源 | 有答案 | 无答案 | 合计 |
|---|---:|---:|---:|
| `internal` | 103 | 45 | 148 |
| `external` | 100 | 0 | 100 |
| 合计 | 203 | 45 | 248 |

无答案题全部来自internal，external没有无答案样本；现有开发集的拒答表现不能推广为external来源上的拒答能力。

3道原无答案题由正文更正为direct：`q_0225`明确说明Skip link应是第一个可聚焦元素；`q_0227`说明KeepAlive默认缓存全部内部实例、可用max设上限；`q_0245`明确说明宽主键可能增加存储开销，足以否定“越宽越好”的前提。其余45题经定向查找相关语料后保留无答案标签并补充缺失信息说明，这不等于独立的全库无答案证明。题型为direct 94、paraphrase 88、multi_block 16、cross_doc 5、no_answer 45；外部组仅direct/paraphrase，两组构成不同。

有答案题由AI辅助逐题阅读题干与规范化原文，标注要点及证据；精确引用、坐标和文档哈希另做机械核验。尚无独立人工验收，不能把机器校验通过写成语义质量认证。修订前区间及范围说明保留在 `evidence_review.jsonl`，不覆盖v1历史复核日志。

当前实测和指标定义统一见 [项目 README](../README.md#新流程实测2026-10-26)。题集结构检查通过，只说明格式和区间等检查未报错，不证明答案充分性或无答案标签已逐题成立。

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

出题后应核对题干的对象、条件和范围，确认全部回答要点都有证据；无答案题要检查全库相关文档及可能的跨段推导，不能仅凭关键词未命中下结论。`check_qrels.py` 检查格式、重复query、文档存在、精确原文与区间范围，v1另查小节相交，并打印题型配比。与建议配比相差超过8个百分点会记录警告；普通模式仅因错误失败，`--strict`会同时因警告失败。当前multi_block比例偏离建议，因此严格模式会失败；配比建议本身也不构成标签质量保证。

## v1历史复核日志

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

2026-10-23日志有218行、218个唯一ID，结论为通过190、修正答案绑定9、跳过18、待定1。它记录v1标注过程；当前v2逐题修订见 `evidence_review.jsonl`。历史记录不能作为新版证据已经验收的证明。

## 开发集与独立验收

现有 248 道题已用于观察行为和开发调整，全部按开发集使用。现在追加 `split` 字段或重新抽取 20% 不能恢复未见测试的独立性；加载器当前也不使用 `split`。

独立验收须在看成绩前固定新题、标注、代码、语料、索引和有效配置，并记录测试反馈是否参与后续修改。[历史原档](../experiments/holdout-v1/README.md)保留不变；用户授权的[证据重标与固定输出重评](../experiments/holdout-evidence-v2/README.md)另存，先冻结标注再读取输出，不称为新的独立盲测。若某题集反馈已用于修改系统，后续分数应作为该集上的回归结果。
