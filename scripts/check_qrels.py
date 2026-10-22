"""校验评测标注 qrels.json：格式、区间合法性、小节对齐、类型配比。

这是「LLM 生成候选 + 人工筛选」之后的质检关。它做四件事：

1. **格式**：借 ``load_qrels`` 校验（query 非空、type 合法、区间 start<end）；
2. **文档存在**：每个答案的 ``doc`` 必须能在 ``data/raw`` 下找到；
3. **区间合法**：``end`` 不能超出规范化后文档长度；区间必须与文档的某个
   ``##`` 小节有重叠（完全落在小节之外通常是手误或复制错了偏移）；
4. **配比**：统计五类 query 的占比，与建议配比对比（direct 30% /
   paraphrase 30% / multi_block 15% / cross_doc 10% / no_answer 15%）。

用法
----
    python scripts/check_qrels.py data/eval/qrels.json
    python scripts/check_qrels.py data/eval/qrels.json --strict   # 有警告也返回非 0

退出码：0 = 通过；1 = 有错误（或 --strict 下有警告）。
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from ragkit.chunking import iter_heading_sections
from ragkit.evaluation import QUERY_TYPES, load_qrels
from ragkit.loaders import load_file
from ragkit.text.normalize import normalize_text

RAW_DIR = Path("data/raw")

# 建议配比（与 README 的评测设计一致）
TARGET_RATIO = {
    "direct": 0.30,
    "paraphrase": 0.30,
    "multi_block": 0.15,
    "cross_doc": 0.10,
    "no_answer": 0.15,
}


def _ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    """命令行入口。"""
    _ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="校验评测标注")
    parser.add_argument("qrels", help="qrels.json 路径")
    parser.add_argument("--strict", action="store_true", help="有警告也视为失败")
    args = parser.parse_args()

    try:
        qrels = load_qrels(Path(args.qrels))
    except (OSError, ValueError, KeyError) as exc:
        print(f"❌ 加载失败：{exc}")
        raise SystemExit(1)

    errors: list[str] = []
    warnings: list[str] = []

    # query 唯一性：重复的题会被算两次，直接虚高指标（实测曾混进 20 条重复，
    # 221 条里只有 201 个不同 query，而当时的质检完全没有发现）
    seen_queries: dict[str, int] = {}
    for i, qrel in enumerate(qrels):
        if qrel.query in seen_queries:
            errors.append(
                f"[{i}] {qrel.query[:24]}: 与第 {seen_queries[qrel.query]} 条 query 重复"
            )
        else:
            seen_queries[qrel.query] = i

    # 文档 → 归一化文本 / 小节区间（只算一次，供区间校验复用）
    section_cache: dict[str, tuple[str, list[tuple[int, int]]]] = {}

    def sections_of(doc: str):
        if doc not in section_cache:
            path = RAW_DIR / doc
            # 必须走 load_file：qrels 的区间是在「剥掉 front matter / HTML 注释 /
            # MDX 标签之后」的文本上算的。直接用 read_text 会差掉上万个码点，
            # 校验会「碰巧通过」而完全失效（实测 23214 vs 8414）。
            loaded = load_file(path)
            normalized = normalize_text(loaded.text)
            section_cache[doc] = (normalized, iter_heading_sections(normalized))
        return section_cache[doc]

    for i, qrel in enumerate(qrels):
        tag = f"[{i}] {qrel.query[:24]}"
        if qrel.is_no_answer:
            if qrel.type != "no_answer":
                errors.append(f"{tag}: 无答案 query 的 type 应为 no_answer，实际 {qrel.type}")
            continue
        if qrel.type == "no_answer":
            errors.append(f"{tag}: type=no_answer 但没有答案区间")

        for ans in qrel.answers:
            path = RAW_DIR / ans.doc
            if not path.exists():
                errors.append(f"{tag}: 文档不存在 {ans.doc}")
                continue
            normalized, sections = sections_of(ans.doc)
            if ans.end > len(normalized):
                errors.append(
                    f"{tag}: 区间 end={ans.end} 超出文档长度 {len(normalized)}（{ans.doc}）"
                )
                continue
            # 区间必须与至少一个小节有重叠
            overlaps = [s for s in sections if ans.start < s[1] and ans.end > s[0]]
            if not overlaps:
                errors.append(
                    f"{tag}: 区间 {ans.start}-{ans.end} 不与任何 ## 小节重叠（{ans.doc}）"
                )
            elif not any(s[0] <= ans.start and ans.end <= s[1] for s in overlaps):
                warnings.append(
                    f"{tag}: 区间跨了多个小节边界（{ans.doc}），请确认是有意为之"
                )

    # 类型配比
    counts = Counter(q.type for q in qrels)
    total = len(qrels) or 1
    print(f"\n总条数 {len(qrels)}（有答案 {sum(1 for q in qrels if not q.is_no_answer)}）")
    print(f"{'类型':<14}{'数量':<7}{'占比':<9}{'建议':<8}")
    print("-" * 40)
    for qtype in QUERY_TYPES:
        count = counts.get(qtype, 0)
        ratio = count / total
        target = TARGET_RATIO[qtype]
        flag = "" if abs(ratio - target) <= 0.08 else "  ← 偏离较大"
        print(f"{qtype:<14}{count:<7}{ratio:<9.1%}{target:<8.0%}{flag}")

    if errors:
        print(f"\n❌ {len(errors)} 个错误：")
        for line in errors[:30]:
            print(f"  - {line}")
    if warnings:
        print(f"\n⚠️ {len(warnings)} 个警告：")
        for line in warnings[:20]:
            print(f"  - {line}")
    if not errors and not warnings:
        print("\n✅ 全部通过")

    if errors or (args.strict and warnings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
