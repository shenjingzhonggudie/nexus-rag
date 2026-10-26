"""跑六组召回与融合对照，打印指标差异，落盘 JSON；真实模型重排均关闭。

前置条件：
1. 已有语料并建过库：``scripts/fetch_docs.py`` → ``ragkit build``；
2. 已有人工标注：``data/eval/qrels.json``（格式见 ``data/README.md``）。

用法::

    # 默认索引（embedding以索引manifest为准）
    python demo_ablation.py

    # 换用另一套索引对比（例如切回 hashing）
    python demo_ablation.py --index-dir data/index.hashing --out reports/ablation.hashing.json

**没有真实标注时不要跑**——旧合成语料上的数字已作废，别再拿来当结论。
"""

import argparse
import json
import sys
from pathlib import Path

from ragkit.config import AppConfig
from ragkit.evaluation import load_qrels, run_ablation
from ragkit.index import load_index

QRELS = Path("data/eval/qrels.json")

# 组名 -> 展示标签。融合方式与真实模型重排状态由实际配置分别展示。
LABELS = {
    "baseline": "baseline (a=0.7)",
    "alpha_09": "a=0.9",
    "alpha_05": "a=0.5",
    "rrf": "rrf",
    "bm25_only": "bm25_only",
    "dense_only": "dense_only",
}


def main() -> None:
    """命令行入口。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="跑消融对照（6 组）")
    parser.add_argument(
        "--index-dir", default=None, help="索引目录；省略时用配置里的 index_dir"
    )
    parser.add_argument(
        "--out", default="reports/ablation.json", help="结果落盘路径"
    )
    args = parser.parse_args()

    if not QRELS.exists():
        raise SystemExit(
            f"缺少 {QRELS}：先按 data/README.md 的流程拉语料并人工标注，再跑消融。"
        )

    cfg = AppConfig()
    index_dir = Path(args.index_dir) if args.index_dir else cfg.index_dir
    print(f"加载索引：{index_dir}")
    built = load_index(
        index_dir,
        provider=cfg.embedding.provider,
        model_name=cfg.embedding.model_name,
    )
    qrels = load_qrels(QRELS)

    results = run_ablation(built, qrels)

    n_answerable = sum(q.is_evaluable and not q.is_no_answer for q in qrels)
    print(f"\n对照组对比（全部{n_answerable}道定稿可答题按题宏平均，非source分组；recall@1~10 + MRR）：")
    ks = list(results["baseline"]["recall_at"].keys())
    print(
        f"{'组':<20}{'fusion':<15}{'model rerank':<15}"
        + "".join(f"{('@' + str(k)):>6}" for k in ks)
        + f"{'MRR':>7}"
    )
    for name, stats in results.items():
        row = "".join(f"{stats['recall_at'][k]:>6.2f}" for k in ks)
        print(
            f"{LABELS.get(name, name):<20}{stats['config']['fusion_method']:<15}"
            f"{('on' if stats['rerank_config']['enabled'] else 'off'):<15}"
            f"{row}{stats['mrr']:>7.3f}"
        )

    base = results["baseline"]
    print("\n召回与融合配置差异（按 recall@1；真实模型重排均关闭）：")
    print(
        f"  dense 腿  = {base['recall_at'][1] - results['bm25_only']['recall_at'][1]:+.3f}"
        f"（默认双路加权融合 vs BM25单路）"
    )
    print(
        f"  BM25 腿   = {base['recall_at'][1] - results['dense_only']['recall_at'][1]:+.3f}"
        f"（默认双路加权融合 vs dense单路）"
    )
    print(
        f"  fusion    = {base['recall_at'][1] - results['rrf']['recall_at'][1]:+.3f}"
        f"（加权 vs 等权 RRF）"
    )
    print(
        f"  alpha=0.9 = {results['alpha_09']['recall_at'][1] - base['recall_at'][1]:+.3f}"
        f"（相对默认 0.7 的变化）"
    )
    print(
        f"  alpha=0.5 = {results['alpha_05']['recall_at'][1] - base['recall_at'][1]:+.3f}"
        f"（相对默认 0.7 的变化）"
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已落盘 {out}")


if __name__ == "__main__":
    main()
