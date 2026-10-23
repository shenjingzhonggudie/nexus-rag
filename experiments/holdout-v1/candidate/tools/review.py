"""候选集自审工具。

职责：
    对生成的候选题做内部重复度检查与覆盖度统计，输出审阅清单。

边界：
    只读取本目录产物与输入语料；不读取 old_queries.jsonl，不调用被测系统。

承诺清单：
    1. 近重复判定用字符 bigram Jaccard 相似度，阈值 0.6 及以上成对列出。
    2. 只报告，不修改任何产物。
"""

from __future__ import annotations

import json
from pathlib import Path

CAND = Path(r"C:\Users\王佳浩\codex\2026-10-23\new-chat\outputs\rag-holdout\candidate")


def bigrams(text: str) -> set[str]:
    """返回文本的字符 bigram 集合。

    Args:
        text: 输入文本。

    Returns:
        bigram 集合。
    """
    return {text[i:i + 2] for i in range(len(text) - 1)}


def main() -> None:
    """执行自审并写出审阅清单。

    Returns:
        None。
    """
    rows = json.loads((CAND / "qrels.candidate.json").read_text(encoding="utf-8"))
    lines = [f"{r['id']} [{r['type']}] {r['query']}" for r in rows]
    pairs: list[str] = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = bigrams(rows[i]["query"]), bigrams(rows[j]["query"])
            sim = len(a & b) / max(1, len(a | b))
            if sim >= 0.6:
                pairs.append(f"{sim:.2f}  {rows[i]['id']} <-> {rows[j]['id']}\n"
                             f"      A: {rows[i]['query']}\n      B: {rows[j]['query']}")
    report = "\n".join(lines) + "\n\n=== 近重复对（阈值 0.60） ===\n" + \
        ("\n".join(pairs) if pairs else "无")
    (CAND / "tools" / "query_list.txt").write_text(report, encoding="utf-8")
    print("queries:", len(rows), "near-dup pairs:", len(pairs))


if __name__ == "__main__":
    main()
