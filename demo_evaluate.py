"""临时演示：用真实语料 + 评测集跑一次完整评测，打印报告。验证完保留。"""

from pathlib import Path
import tempfile

from ragkit.config import AppConfig
from ragkit.evaluation import load_qrels
from ragkit.evaluation.report import evaluate
from ragkit.index import build

ROOT = Path("data")
cfg = AppConfig(index_dir=Path(tempfile.mkdtemp(prefix="eval-index-")))
print("建库中…")
built = build(ROOT / "raw", cfg)
qrels = load_qrels(ROOT / "eval" / "qrels.json")

report = evaluate(built, cfg, qrels)

print(f"评测集 {len(report.per_query)} 条")
print("recall@k 曲线: " + "  ".join(f"@{k}={v:.3f}" for k, v in report.recall_at.items()))
print(f"MRR      = {report.mrr:.3f}")
print(
    f"耗时  冷启动 {report.latency.cold_ms:.0f}ms | 热启动均值 {report.latency.warm_mean_ms:.1f}ms"
    f" P50 {report.latency.warm_p50_ms:.1f}ms P95 {report.latency.warm_p95_ms:.1f}ms"
)
print("\n逐条明细（query → 命中/总相关）：")
for q in report.per_query:
    top = q.retrieved[0] if q.retrieved else "-"
    print(f"  {q.query[:18]:<18} | top1={top:<16} | mrr={q.mrr:.2f}")
