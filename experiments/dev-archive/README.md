# 开发集快照

保存某一版开发集的**原始字节**，供追溯当期评测数字使用。

| 项 | 值 |
|---|---|
| 文件 | `qrels.snapshot.json` |
| 格式 | v2（回答要点 + 最小充分证据） |
| 字节哈希 | 见 `data/eval/annotation_manifest.json` 的 `previous_qrels_sha256` |

**这不是当前评测集。** 当前评测集见 `data/eval/qrels.json`（310 题）。
保留这份快照是为了让历史报告里的数字仍能对应到当时的输入，不是供日常评测使用。

```powershell
# 用历史快照重跑当期评测（如需对照）
.\.venv\Scripts\ragkit.exe eval --qrels experiments/dev-archive/qrels.snapshot.json --out reports/eval.snapshot.json
```
