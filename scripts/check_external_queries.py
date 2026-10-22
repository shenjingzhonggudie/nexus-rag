"""校验「只看标题出题」任务的产出。

检查项
------
1. **id 覆盖**：标题清单里的每个 id 都要出现且只出现一次；
2. **长度**：非 skip 条目 10~35 个汉字（含标点 ≤ 40 字符）；
3. **类型**：`direct` / `paraphrase` 二选一；
4. **复用限制**：`paraphrase` 不得含标题里连续 4 个汉字、`direct` 不得含连续 6 个汉字
   （防止把标题原样改成问句）；
5. **skip 说明**：skip 条目必须写 reason。

用法
----
    python scripts/check_external_queries.py external_queries.json
    python scripts/check_external_queries.py external_queries.json --strict

退出码：0 = 通过；1 = 有错误（或 --strict 下有警告）。
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# 默认指向当前在用的第二批；第一批的标题清单已随产出一起移除（数据已过期）
TITLES_FILE = Path("data/eval/independent_titles_batch2.json")

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")
_PARAPHRASE_MIN_REUSE = 4   # paraphrase 允许的标题最长复用片段
_DIRECT_MIN_REUSE = 6       # direct 允许的标题最长复用片段


def _ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _chinese_count(text: str) -> int:
    return sum(1 for char in text if "\u4e00" <= char <= "\u9fff")


def shared_fragments(title: str, query: str, min_len: int) -> list[str]:
    """返回标题中长度 ≥ min_len、且出现在 query 里的连续汉字片段。

    Args:
        title: 小节标题。
        query: 待检查的问题。
        min_len: 最短片段长度（片段越长越像"整句照搬"）。

    Returns:
        list[str]: 命中的片段（去重、排序）；无命中为空列表。
    """
    hits: set[str] = set()
    for run in _CJK_RUN.findall(title):
        for i in range(len(run) - min_len + 1):
            fragment = run[i : i + min_len]
            if fragment in query:
                hits.add(fragment)
    return sorted(hits)


def main() -> None:
    """命令行入口。"""
    _ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="校验外部 agent 的题目产出")
    parser.add_argument("output", help="JSON 文件路径")
    parser.add_argument(
        "--titles",
        default=str(TITLES_FILE),
        help="标题清单 JSON（默认 independent_titles_batch2.json）",
    )
    parser.add_argument("--strict", action="store_true", help="有警告也视为失败")
    args = parser.parse_args()

    titles = {
        item["id"]: item
        for item in json.loads(Path(args.titles).read_text(encoding="utf-8"))
    }
    try:
        rows = json.loads(Path(args.output).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"❌ 无法解析 {args.output}：{exc}")
        raise SystemExit(1)
    if not isinstance(rows, list):
        print("❌ 顶层必须是 JSON 数组")
        raise SystemExit(1)

    errors: list[str] = []
    warnings: list[str] = []
    seen: Counter = Counter()

    for item in rows:
        if not isinstance(item, dict):
            errors.append(f"非对象条目：{item!r}")
            continue
        item_id = item.get("id")
        if item_id not in titles:
            errors.append(f"未知 id：{item_id}")
            continue
        seen[item_id] += 1
        title = titles[item_id]["section"]

        if item.get("skip"):
            if not str(item.get("reason", "")).strip():
                errors.append(f"[{item_id}] skip 但没写 reason")
            continue

        query = str(item.get("query", "")).strip()
        qtype = item.get("type")
        if not query:
            errors.append(f"[{item_id}] 既没有 query 也没标 skip")
            continue
        if qtype not in ("direct", "paraphrase"):
            errors.append(f"[{item_id}] type 非法：{qtype!r}")
            continue

        chars = _chinese_count(query)
        if not (10 <= chars <= 35):
            warnings.append(f"[{item_id}] 汉字数 {chars}（建议 10~35）：{query}")
        if len(query) > 40:
            warnings.append(f"[{item_id}] 总长 {len(query)} 字符（建议 ≤ 40）：{query}")
        if query.count("？") + query.count("?") > 1:
            warnings.append(f"[{item_id}] 含多个问号：{query}")

        min_len = (
            _PARAPHRASE_MIN_REUSE if qtype == "paraphrase" else _DIRECT_MIN_REUSE
        )
        reused = shared_fragments(title, query, min_len)
        if reused:
            errors.append(
                f"[{item_id}] {qtype} 复用了标题片段 {reused}："
                f"标题={title!r} query={query!r}"
            )

    # id 覆盖
    missing = sorted(set(titles) - set(seen))
    duplicated = sorted(i for i, n in seen.items() if n > 1)
    if missing:
        errors.append(f"缺少 id：{missing}")
    if duplicated:
        errors.append(f"重复 id：{duplicated}")

    # 汇总
    skipped = sum(1 for item in rows if isinstance(item, dict) and item.get("skip"))
    types = Counter(
        item.get("type")
        for item in rows
        if isinstance(item, dict) and not item.get("skip")
    )
    print(f"总条数 {len(rows)}（skip {skipped}，有效 {len(rows) - skipped}）")
    print(f"类型分布：{dict(types)}")
    if types:
        ratio = types.get("paraphrase", 0) / max(sum(types.values()), 1)
        print(f"paraphrase 占比 {ratio:.0%}（任务要求约 50%）")

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
