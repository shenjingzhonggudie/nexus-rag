"""列出文档的小节及其字符区间，供人工选题、写 query 与标注。

标注格式是「文档 + 小节字符区间」，所以写 qrels 时需要知道每个小节的
``start`` / ``end``。本脚本直接把它们列出来，避免手工数偏移。

用法
----
    python scripts/section_index.py                  # 列出 data/raw 下全部小节
    python scripts/section_index.py --doc k8s/a.md   # 只看一篇
    python scripts/section_index.py --json           # 输出 JSON（供后续脚本消费）
    python scripts/section_index.py --max-chars 1000 # 只列长度不超过 1000 的小节

输出每行：文档 | 小节序号 | 字符区间 | 标题 | 前 60 字摘要。
序号是该文档内 ``##`` 小节的顺序（从 0 起），与 ``iter_heading_sections`` 一致。
"""

import argparse
import json
import sys
from pathlib import Path

from ragkit.chunking import iter_heading_sections
from ragkit.text import clean_heading
from ragkit.text.normalize import normalize_text

RAW_DIR = Path("data/raw")


def _ensure_utf8_stdout() -> None:
    """Windows 控制台默认 GBK，中文/长文本容易崩，这里强制 UTF-8。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def iter_sections(path: Path, rel: str):
    """逐个产出 (rel, index, heading, start, end, body)。"""
    text = path.read_text(encoding="utf-8")
    normalized = normalize_text(text)
    for index, (start, end) in enumerate(iter_heading_sections(normalized)):
        body = normalized[start:end]
        first_line = body.splitlines()[0] if body else ""
        heading = clean_heading(first_line)
        yield rel, index, heading, start, end, body


def main() -> None:
    """命令行入口。"""
    _ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="列出文档小节及字符区间")
    parser.add_argument("--doc", default="", help="只看指定文档（相对 data/raw 的路径）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非表格")
    parser.add_argument(
        "--max-chars", type=int, default=0, help="只列长度不超过该值的小节（0 = 不限）"
    )
    args = parser.parse_args()

    if not RAW_DIR.exists():
        print(f"没有找到 {RAW_DIR}，请先运行 scripts/fetch_docs.py")
        return

    docs = (
        [RAW_DIR / args.doc]
        if args.doc
        else sorted(RAW_DIR.rglob("*.md"))
    )

    rows = []
    for path in docs:
        if not path.exists():
            print(f"文档不存在：{path}")
            continue
        rel = path.relative_to(RAW_DIR).as_posix()
        for rel_doc, index, heading, start, end, body in iter_sections(path, rel):
            if args.max_chars and (end - start) > args.max_chars:
                continue
            rows.append(
                {
                    "doc": rel_doc,
                    "index": index,
                    "heading": heading,
                    "start": start,
                    "end": end,
                    "chars": end - start,
                    "preview": body.replace("\n", " ")[:80],
                }
            )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    print(f"{'doc':<34}{'#':<4}{'区间':<14}{'字数':<7}标题")
    print("-" * 100)
    for row in rows:
        span = f"{row['start']}-{row['end']}"
        print(
            f"{row['doc'][:32]:<34}{row['index']:<4}{span:<14}"
            f"{row['chars']:<7}{row['heading'][:30]}"
        )
    print(f"\n共 {len(rows)} 个小节（{len(docs)} 篇文档）")
    print("写标注时直接抄「区间」两端的数字作为 start / end。")


if __name__ == "__main__":
    main()
