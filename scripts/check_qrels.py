"""机械校验qrels：格式、精确原文、区间合法性及类型配比。

检查通过不代表回答要点充分，也不代表已完成人工审核。检查内容：

1. **格式**：借 ``load_qrels`` 校验（query 非空、type 合法、区间 start<end）；
2. **文档存在**：每个答案的 ``doc`` 必须能在 ``data/raw`` 下找到；
3. **证据与区间**：v2的quote须与原文切片完全一致；``end`` 不得超出文档长度。
   只有v1继续检查小节对齐；v2允许使用导语、标题附近的充分证据。
4. **配比**：统计五类 query 的占比，与建议配比对比（direct 30% /
   paraphrase 30% / multi_block 15% / cross_doc 10% / no_answer 15%）；
   绝对偏离超过8个百分点记为警告，恰好8个百分点不警告。

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
    if len({q.annotation_version for q in qrels}) > 1:
        errors.append("不可混合v1与v2标注；evaluate无法按同一口径汇总")

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
        if not qrel.is_evaluable:
            warnings.append(f"{tag}: 证据标注仍需复核，不计入评测分母")
            continue
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
            if qrel.annotation_version == 2 and normalized[ans.start:ans.end] != ans.quote:
                errors.append(f"{tag}: quote 与规范化原文区间不一致（{ans.doc}）")
            if qrel.annotation_version == 2:
                continue  # 精确证据不必等于小节，也允许位于首个##标题之前
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
    v2 = [q for q in qrels if q.annotation_version == 2]
    if v2:
        print(f"v2回答要点 {sum(len(q.answer_points) for q in v2)}；"
              f"证据片段 {sum(len(q.answers) for q in v2)}；"
              f"待复核 {sum(not q.is_evaluable for q in v2)}")
    print(f"{'类型':<14}{'数量':<7}{'占比':<9}{'建议':<8}")
    print("-" * 40)
    for qtype in QUERY_TYPES:
        count = counts.get(qtype, 0)
        ratio = count / total
        target = TARGET_RATIO[qtype]
        # 建议值均为整数百分数；交叉相乘避免8个百分点边界的浮点误差。
        deviates = abs(count * 100 - round(target * 100) * total) > 8 * total
        flag = "  ← 偏离较大" if deviates else ""
        print(f"{qtype:<14}{count:<7}{ratio:<9.1%}{target:<8.0%}{flag}")
        if deviates:
            warnings.append(
                f"题型配比 {qtype}: 实际 {ratio:.1%}，建议 {target:.0%}，"
                "偏离超过8个百分点"
            )

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
