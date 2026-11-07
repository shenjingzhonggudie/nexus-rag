# 独立盲测集（当前为空）

> **状态：这里没有任何真正的盲测案例。** `qrels.blind.json` 是空数组 `[]`。
> 建立这个目录只是先把接口、格式与隔离约定定下来，不代表已拥有盲测集。

## 为什么单独放一个目录

回归集（`data/eval/qrels.regression.json`，310 题）由两批**已经参与过开发反馈**的题组成：

| origin | 条数 | 情况 |
|---|---:|---|
| `original_248` | 248 | 开发过程中反复使用 |
| `original_62` | 62 | 先冻结后查看输出，但**反馈已进入开发循环** |

这两批都不能再称为独立盲测。把盲测集放在**独立目录 + 独立文件**，是为了让"这批题有没有被开发过程污染"这件事在文件层面就可见，而不是靠记忆。

## 硬性要求

新增盲测案例必须同时满足：

1. **独立来源**：由不了解本项目实现的人/流程编写，只拿到语料与格式说明，不参考回归集题目。
2. **不得由回归案例改写**：不能把 248 / 62 里的题换措辞、换角度后当作"新题"。
3. **先冻结**：题干、标注、评分口径在**第一次看系统输出之前**固化成文件并记录哈希。
4. **开发期不读**：开发阶段不读盲测输出、不据此调 Prompt / 参数 / 工具描述。一旦读了并据此修改，这批数据就降级为回归集。
5. **不混算**：盲测结果单独出报告，**不与回归成绩合并成一个数字**。

## 文件格式

`qrels.blind.json` 与 `data/eval/qrels.json` 结构一致（v2 口径），额外要求：

```json
{
  "id": "b_0001",
  "query": "...",
  "type": "direct | paraphrase | multi_block | cross_doc | no_answer",
  "source": "blind",
  "origin": "blind",
  "annotation_version": 2,
  "annotation_status": "complete",
  "answers": [
    {"point": "...", "evidence": [{"doc": "...", "section": "...", "start": 0, "end": 10, "quote": "..."}]}
  ]
}
```

- `id` 用 `b_` 前缀，与回归集的 `q_` / `h_` 不冲突
- `origin` 固定为 `blind`
- `annotation_status=needs_review` 的题不进入主指标分母（与回归集一致）

## 校验

```powershell
# 格式与区间合法性（与回归集同一套检查）
.\.venv\Scripts\python.exe scripts/check_qrels.py data/eval/blind/qrels.blind.json

# 隔离性：盲测集不得与回归集重叠
.\.venv\Scripts\python.exe -m pytest tests/test_blind_suite.py -q
```

## 当前缺什么

| 缺项 | 说明 |
|---|---|
| **案例本身** | 需要独立出题流程产出一批新题，本次不做 |
| **独立标注** | 每道题的要点与最小充分证据须由出题方标注，不能用回归集的 |
| **冻结记录** | 首次运行前需记录 `qrels.blind.json` 的 SHA-256 与冻结时间 |
| **物理隔离（可选）** | 若要防止开发 agent 读取，可放到独立仓库或加密归档；同仓库明文只靠约定约束 |

## 与回归集的关系

```
data/eval/qrels.regression.json   310 题   已参与反馈，只用于回归
data/eval/blind/qrels.blind.json    0 题   独立盲测，当前为空
```

**两份文件的成绩不能相加、不能平均、不能互相替代。**
