"""临时演示：跑 4 组消融对照，打印对比表 + 边际贡献，落盘 reports/ablation.json。"""

import json
from pathlib import Path

from ragkit.config import AppConfig
from ragkit.evaluation import load_qrels, run_ablation
from ragkit.index import load_index

cfg = AppConfig()
print("加载索引中…")
built = load_index(cfg.index_dir)
qrels = load_qrels(Path("data/eval/qrels.json"))

results = run_ablation(built, qrels)

print("\n对照组对比（recall@1~10 + MRR）：")
ks = list(results["baseline"]["recall_at"].keys())
print(f"{'组':<12}" + "".join(f"{('@'+str(k)):>6}" for k in ks) + f"{'MRR':>7}")
for name, r in results.items():
    row = "".join(f"{r['recall_at'][k]:>6.2f}" for k in ks)
    print(f"{name:<12}{row}{r['mrr']:>7.3f}")

base = results["baseline"]
print("\n各组件边际贡献（baseline 减去关掉它，按 recall@1）：")
print(f"  dense 腿 = {base['recall_at'][1] - results['bm25_only']['recall_at'][1]:+.3f}")
print(f"  BM25 腿 = {base['recall_at'][1] - results['dense_only']['recall_at'][1]:+.3f}")
print(f"  rerank  = {base['recall_at'][1] - results['no_rerank']['recall_at'][1]:+.3f}")

out = Path("reports/ablation.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n已落盘 {out}")
