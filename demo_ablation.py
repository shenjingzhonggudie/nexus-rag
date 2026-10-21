"""跑消融对照（4 组单变量），打印对比表 + 边际贡献，落盘 reports/ablation.json。

前置条件：
1. 已有语料并建过库：``scripts/fetch_docs.py`` → ``ragkit build``；
2. 已有人工标注：``data/eval/qrels.json``（格式见 ``data/README.md``）。

**没有真实标注时不要跑**——旧合成语料上的数字已作废，别再拿来当结论。
"""

import json
from pathlib import Path

from ragkit.config import AppConfig
from ragkit.evaluation import load_qrels, run_ablation
from ragkit.index import load_index

QRELS = Path("data/eval/qrels.json")
if not QRELS.exists():
    raise SystemExit(
        f"缺少 {QRELS}：先按 data/README.md 的流程拉语料并人工标注，再跑消融。"
    )

cfg = AppConfig()
print("加载索引中…")
built = load_index(
    cfg.index_dir,
    provider=cfg.embedding.provider,
    model_name=cfg.embedding.model_name,
)
qrels = load_qrels(QRELS)

results = run_ablation(built, qrels)

# 组名 -> 展示标签 / rerank 状态：baseline 是"默认全开"，不是"无处理基线"，
# 表里必须标出来，否则很容易被误读成最保守的配置。
LABELS = {
    "baseline": "baseline (all on)",
    "no_rerank": "no_rerank (RRF)",
    "bm25_only": "bm25_only",
    "dense_only": "dense_only",
}
RERANK_STATE = {
    "baseline": "on(weighted)",
    "no_rerank": "off(even)",
    "bm25_only": "off",
    "dense_only": "off",
}

print("\n对照组对比（recall@1~10 + MRR）：")
ks = list(results["baseline"]["recall_at"].keys())
print(f"{'组':<26}{'rerank':<12}" + "".join(f"{('@'+str(k)):>6}" for k in ks) + f"{'MRR':>7}")
for name, r in results.items():
    row = "".join(f"{r['recall_at'][k]:>6.2f}" for k in ks)
    print(
        f"{LABELS.get(name, name):<26}{RERANK_STATE.get(name, '?'):<12}"
        f"{row}{r['mrr']:>7.3f}"
    )

print(
    "\n注：baseline = 默认全开（加权排名融合），不是'无处理基线'；"
    "no_rerank = 关掉它、退化成等权 RRF"
)

base = results["baseline"]
print("\n各组件边际贡献（按 recall@1；正 = 有帮助，负 = 帮倒忙）：")
print(f"  dense 腿 = {base['recall_at'][1] - results['bm25_only']['recall_at'][1]:+.3f}（关掉 dense 的损失）")
print(f"  BM25 腿  = {base['recall_at'][1] - results['dense_only']['recall_at'][1]:+.3f}（关掉 BM25 的损失）")
print(f"  rerank  = {base['recall_at'][1] - results['no_rerank']['recall_at'][1]:+.3f}（加权排名融合相对等权 RRF 的增益）")

out = Path("reports/ablation.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n已落盘 {out}")
