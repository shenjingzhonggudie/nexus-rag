"""构建 310 题回归评测集：248（原开发集）+ 62（原留出集 v2 重标）。

只做两件事：给每条加上 `origin` 标记，然后把两份按原顺序拼接。
**不修改任何原有字段**（query / answers / type / source / annotation_*），
也不删除任何案例。

输出：data/eval/qrels.regression.json（LF、indent=2，与现有 qrels.json 一致）

用法：
    .\\.venv\\Scripts\\python.exe scripts/build_regression_suite.py
    .\\.venv\\Scripts\\python.exe scripts/build_regression_suite.py --check   # 只校验不写
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "eval" / "qrels.json"
HOLDOUT_V2 = ROOT / "experiments" / "holdout-evidence-v2" / "qrels.v2.json"
OUT = ROOT / "data" / "eval" / "qrels.regression.json"

ORIGIN_DEV = "original_248"
ORIGIN_HOLDOUT = "original_62"
EXPECTED_TOTAL = 310


def _load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: 顶层必须是列表")
    return data


def build() -> list[dict]:
    """返回合并后的 310 条（不写盘）。"""
    dev = _load(DEV)
    hold = _load(HOLDOUT_V2)

    for item in dev:
        item["origin"] = ORIGIN_DEV
    for item in hold:
        item["origin"] = ORIGIN_HOLDOUT

    merged = dev + hold

    # —— 校验：任何一条不满足就抛错，不写出半成品 ——
    ids = [item.get("id") for item in merged]
    if not all(ids):
        missing = [i for i, q in enumerate(merged) if not q.get("id")]
        raise ValueError(f"存在缺 id 的条目，下标 {missing[:5]}")

    dup = [k for k, v in Counter(ids).items() if v > 1]
    if dup:
        raise ValueError(f"id 重复: {dup[:10]}")

    versions = {item.get("annotation_version") for item in merged}
    if versions != {2}:
        raise ValueError(f"合并后口径不一致: annotation_version={versions}（必须全为 2）")

    origins = Counter(item["origin"] for item in merged)
    if set(origins) != {ORIGIN_DEV, ORIGIN_HOLDOUT}:
        raise ValueError(f"origin 取值异常: {dict(origins)}")

    if len(merged) != EXPECTED_TOTAL:
        raise ValueError(f"总条数 {len(merged)} != {EXPECTED_TOTAL}")

    # query 文本完全重复也要报出来（本题集当前为 0，若将来出现需人工判断）
    texts = Counter(str(item.get("query", "")).strip() for item in merged)
    repeated = [t for t, n in texts.items() if n > 1]
    if repeated:
        raise ValueError(f"query 文本重复 {len(repeated)} 条，需人工确认: {repeated[:3]}")

    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = parser.parse_args(argv)

    merged = build()
    origins = Counter(item["origin"] for item in merged)
    types = Counter(item.get("type") for item in merged)
    answerable = sum(1 for item in merged if item.get("type") != "no_answer")
    pending = sum(
        1 for item in merged if item.get("annotation_status") == "needs_review"
    )

    print(f"合并完成：{len(merged)} 条")
    print(f"  origin : {dict(origins)}")
    print(f"  type   : {dict(types)}")
    print(f"  有答案 {answerable}  无答案 {len(merged) - answerable}  待复核 {pending}")

    if args.check:
        if not OUT.exists():
            print(f"\n[--check] {OUT.name} 尚未生成")
            return 1
        on_disk = _load(OUT)
        same = on_disk == merged
        print(f"\n[--check] 磁盘文件 {len(on_disk)} 条，与重新构建一致: {same}")
        return 0 if same else 1

    OUT.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n已写出 {OUT.relative_to(ROOT).as_posix()}（{OUT.stat().st_size / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
