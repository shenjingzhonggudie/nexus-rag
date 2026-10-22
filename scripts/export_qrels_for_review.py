"""把 qrels 展开成「query + 对应原文片段」，供人工或另一个 agent 逐条核对。

为什么要这个脚本：``qrels.json`` 里的答案是「文档 + 字符区间」，直接看区间看不出
内容。而且区间基于 ``normalize_text(load_file(doc).text)``——剥离了 front matter、
HTML 注释、MDX 标签之后的文本，**不能拿原始文件按下标去切**。

输出一个 Markdown 文件，每条标注给出：
- **稳定样本 ID**（`q_0042`，供 ``review_log.jsonl`` 关联）、query、类型、来源
- 答案所在文档、小节名
- 该区间对应的正文（截断到 600 字，够判断主题）

用法::

    python scripts/export_qrels_for_review.py
    python scripts/export_qrels_for_review.py --out review.md --chars 800
"""

import argparse
import json
import sys
from pathlib import Path

from ragkit.loaders import load_file
from ragkit.text.normalize import normalize_text

RAW_DIR = Path("data/raw")
QRELS = Path("data/eval/qrels.json")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="导出 qrels 供人工核对")
    parser.add_argument("--qrels", default=str(QRELS), help="qrels.json 路径")
    parser.add_argument("--out", default="_qrels_review.md", help="输出 Markdown 路径")
    parser.add_argument("--chars", type=int, default=600, help="每条正文截断字数")
    args = parser.parse_args()

    qrels = json.loads(Path(args.qrels).read_text(encoding="utf-8"))

    doc_cache: dict[str, str] = {}

    def normalized(doc: str) -> str:
        if doc not in doc_cache:
            loaded = load_file(RAW_DIR / doc)
            doc_cache[doc] = normalize_text(loaded.text)
        return doc_cache[doc]

    lines: list[str] = [
        "# 评测标注核对表",
        "",
        "每条给出「问题」与「该问题标注的答案原文」。请判断：**这段原文是否回答了这个问题**。",
        "",
        "> 坐标说明：`start`/`end` 是**规范化文本**（剥掉 front matter / HTML 注释 / MDX 标签后）",
        "> 的码点下标，不要用原始文件按下标重切——正文已直接附在下面。",
        "",
        f"共 {len(qrels)} 条。",
        "",
    ]

    for i, item in enumerate(qrels):
        answers = item.get("answers", [])
        sample_id = item.get("id") or f"q_{i:04d}"
        lines.append(f"## [{sample_id}] {item['query']}")
        lines.append("")
        lines.append(f"- type: `{item['type']}`  |  source: `{item.get('source', '?')}`")
        if not answers:
            lines.append("- **无答案**（`no_answer` 类，用于测拒答）")
            lines.append("")
            continue
        for label, ans in zip("ABCD", answers):
            text = normalized(ans["doc"])[ans["start"] : ans["end"]]
            snippet = text[: args.chars].strip()
            if len(text) > args.chars:
                snippet += " …"
            lines.append(f"- **答案 {label}**：`{ans['doc']}`")
            lines.append(f"  - section: `{ans['section']}`  区间 `[{ans['start']}, {ans['end']})`")
            lines.append("")
            lines.append("```text")
            lines.append(snippet)
            lines.append("```")
            lines.append("")

    out = Path(args.out)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"已导出 {len(qrels)} 条 -> {out}（{out.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
