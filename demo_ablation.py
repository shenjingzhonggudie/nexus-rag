"""跑消融对照（6 组单变量），打印对比表 + 边际贡献，落盘 JSON。

前置条件：
1. 已有语料并建过库：``scripts/fetch_docs.py`` → ``ragkit build``；
2. 已有人工标注：``data/eval/qrels.json``（格式见 ``data/README.md``）。

用法::

    # 默认索引（当前配置的 embedding，通常是 bge）
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

# 组名 -> 展示标签 / rerank 状态。
# baseline 是"默认全开"，不是"无处理基线"，表里必须标出来，否则容易被误读。
LABELS = {
    "baseline": "baseline (a=0.9)",
    "alpha_08": "a=0.8",
    "alpha_07": "a=0.7",
    "no_rerank": "no_rerank (RRF)",
    "bm25_only": "bm25_only",
    "dense_only": "dense_only",
}
RERANK_STATE = {
    "baseline": "on(weighted)",
    "alpha_08": "on(weighted)",
    "alpha_07": "on(weighted)",
    "no_rerank": "off(even)",
    "bm25_only": "off",
    "dense_only": "off",
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

    print("\n对照组对比（recall@1~10 + MRR）：")
    ks = list(results["baseline"]["recall_at"].keys())
    print(
        f"{'组':<20}{'rerank':<13}"
        + "".join(f"{('@' + str(k)):>6}" for k in ks)
        + f"{'MRR':>7}"
    )
    for name, stats in results.items():
        row = "".join(f"{stats['recall_at'][k]:>6.2f}" for k in ks)
        print(
            f"{LABELS.get(name, name):<20}{RERANK_STATE.get(name, '?'):<13}"
            f"{row}{stats['mrr']:>7.3f}"
        )

    base = results["baseline"]
    print("\n各组件边际贡献（按 recall@1；正 = 有帮助，负 = 帮倒忙）：")
    print(
        f"  dense 腿  = {base['recall_at'][1] - results['bm25_only']['recall_at'][1]:+.3f}"
        f"（关掉 dense 的损失）"
    )
    print(
        f"  BM25 腿   = {base['recall_at'][1] - results['dense_only']['recall_at'][1]:+.3f}"
        f"（关掉 BM25 的损失）"
    )
    print(
        f"  rerank    = {base['recall_at'][1] - results['no_rerank']['recall_at'][1]:+.3f}"
        f"（加权 vs 等权 RRF）"
    )
    print(
        f"  alpha=0.8 = {results['alpha_08']['recall_at'][1] - base['recall_at'][1]:+.3f}"
        f"（相对 0.9 的变化）"
    )
    print(
        f"  alpha=0.7 = {results['alpha_07']['recall_at'][1] - base['recall_at'][1]:+.3f}"
        f"（相对 0.9 的变化）"
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已落盘 {out}")


if __name__ == "__main__":
    main()
