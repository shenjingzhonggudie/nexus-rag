"""出题辅助：为指定小节生成「让 LLM 出题」的 prompt（LLM 生成 + 人工筛选第一步）。

为什么做成"打印 prompt"而不是"直接调 API"
----------------------------------------
出题这一步要**人工把关**，而且不该用同一个 LLM 既出题又当生成端（否则评测
偏乐观）。所以本脚本只负责把「小节内容 + 出题要求」组装成一段可直接粘贴给
任意 LLM 的 prompt，输出候选 JSON，再由人挑、改、筛。这样：
- 不绑定某家模型，换模型零成本；
- prompt 本身可存档，评审时能看到出题标准；
- 人始终在环里（面试可以讲"我人工筛过"）。

用法
----
    python scripts/gen_queries.py --list                 # 列出可选题的小节
    python scripts/gen_queries.py --prompt 3             # 第 3 个小节的出题 prompt
    python scripts/gen_queries.py --prompt 3 --type paraphrase
    python scripts/gen_queries.py --doc k8s/a.md --prompt 0

拿到 LLM 输出后：
1. 删掉"照抄原文用词"的题（那是 direct，占 30% 够了，别全是）；
2. 删掉答案不唯一、有歧义的题；
3. 把保留的题连同 ``doc/section/start/end`` 填进 ``data/eval/qrels.json``；
4. 跑 ``python scripts/check_qrels.py data/eval/qrels.json`` 做质检。
"""

import argparse
import sys
from pathlib import Path

from ragkit.chunking import iter_heading_sections
from ragkit.text import clean_heading
from ragkit.text.normalize import normalize_text

RAW_DIR = Path("data/raw")

# 各类型的出题要求：写成 prompt 的一部分，让 LLM 按统一口径出题
TYPE_GUIDE = {
    "direct": "用文档里出现的关键术语直接发问，能一眼看出对应哪一节。",
    "paraphrase": "换一种说法，**不要照抄原文的术语**，用同义表达或描述现象的方式发问。",
    "multi_block": "问题需要综合两三个小节才能回答（答案分散），不是单节能答完的。",
    "cross_doc": "问题需要对比不同文档里的内容才能回答。",
}

PROMPT_TEMPLATE = """你是一个技术文档问答数据集的出题人。请只依据下面的小节内容出题。

要求：
1. {guide}
2. 问题必须是**这个语料能回答**的，不要引入小节之外的知识。
3. 问题要具体、无歧义，答案唯一。
4. 输出的问题不要出现"这段文字""本小节"之类的元指代。
5. 出 {count} 个问题，每行一个，不要编号、不要解释。

小节标题：{heading}
小节内容：
---
{body}
---
"""


def _ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _collect(doc_filter: str) -> list[dict]:
    """收集所有 (doc, index, heading, start, end, body)。"""
    docs = [RAW_DIR / doc_filter] if doc_filter else sorted(RAW_DIR.rglob("*.md"))
    rows: list[dict] = []
    for path in docs:
        if not path.exists():
            continue
        rel = path.relative_to(RAW_DIR).as_posix()
        normalized = normalize_text(path.read_text(encoding="utf-8"))
        for index, (start, end) in enumerate(iter_heading_sections(normalized)):
            body = normalized[start:end]
            heading = clean_heading(body.splitlines()[0]) if body else ""
            rows.append(
                {
                    "doc": rel,
                    "index": index,
                    "heading": heading,
                    "start": start,
                    "end": end,
                    "body": body,
                }
            )
    return rows


def main() -> None:
    """命令行入口。"""
    _ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="为小节生成出题 prompt")
    parser.add_argument("--list", action="store_true", help="列出所有小节")
    parser.add_argument("--doc", default="", help="限定文档（相对 data/raw）")
    parser.add_argument("--prompt", type=int, default=-1, help="为第几个小节出题")
    parser.add_argument(
        "--type", default="paraphrase", choices=list(TYPE_GUIDE), help="出题类型"
    )
    parser.add_argument("--count", type=int, default=2, help="让 LLM 出几个问题")
    args = parser.parse_args()

    rows = _collect(args.doc)
    if not rows:
        print(f"没有找到文档，请先运行 scripts/fetch_docs.py（目录 {RAW_DIR}）")
        return

    if args.list:
        print(f"{'#':<5}{'doc':<34}{'区间':<14}标题")
        print("-" * 92)
        for i, row in enumerate(rows):
            print(
                f"{i:<5}{row['doc'][:32]:<34}"
                f"{row['start']}-{row['end']:<10}{row['heading'][:28]}"
            )
        print(f"\n共 {len(rows)} 个小节；用 --prompt <编号> 生成出题 prompt")
        return

    if args.prompt < 0:
        print("请指定 --prompt <编号>，或先用 --list 查看编号")
        return
    if args.prompt >= len(rows):
        print(f"编号越界：只有 {len(rows)} 个小节")
        return

    row = rows[args.prompt]
    print(PROMPT_TEMPLATE.format(
        guide=TYPE_GUIDE[args.type],
        count=args.count,
        heading=row["heading"],
        body=row["body"],
    ))
    print("=" * 60)
    print("拿到问题后，这条标注要填的字段是：")
    print(f'  "doc": "{row["doc"]}"')
    print(f'  "section": "{row["heading"]}"')
    print(f'  "start": {row["start"]}')
    print(f'  "end": {row["end"]}')


if __name__ == "__main__":
    main()
