"""程序化生成语料与块级评测集。

语料：20 主题 × 5 篇（1 正 + 4 误导），每篇约 10000 字（约 30 个 ## 小节）。
分块：heading 策略（每个 ## 小节一个 chunk，块级标注的基础）。
评测：块级标注——relevant = 答案小节的 chunk_id。三类 query：
  - direct：直接问主题概念；
  - paraphrase：改写措辞、不直接搬概念词；
  - no_answer：语料里没有答案，relevant 为空（测拒答）。

用法：在项目根运行 `python scripts/generate_corpus.py`。
"""

import json
from pathlib import Path

from ragkit.chunking import chunk_document, iter_heading_sections
from ragkit.schemas import Document
from ragkit.text.normalize import normalize_text

from corpus_data import TOPICS

RAW = Path("data/raw")
EVAL = Path("data/eval")


def build_md(title: str, sections: list[tuple[str, str]]) -> str:
    """组装 Markdown 文本：# 一级标题 + 若干 ## 小节。"""
    parts = [f"# {title}"]
    for heading, body in sections:
        parts.append(f"## {heading}\n\n{body}")
    return "\n\n".join(parts) + "\n"


def section_chunk_ids(doc_id: str, md_text: str) -> list[list[str]]:
    """返回每个 ## 小节对应的 chunk_id 列表（超长小节被再切时对应多个块）。

    先按 heading 得到每个原始小节的区间，再用 chunk_document 切分，把每个
    chunk 按 char_start 归到所属小节。这样答案小节的 relevant 就是它覆盖的
    全部块，而不是依赖"小节序号 == 块索引"这个在再切后不成立的假设。
    """
    normalized = normalize_text(md_text)
    doc = Document(doc_id=doc_id, source=doc_id, text=md_text, title=doc_id)
    chunks = chunk_document(doc, strategy="heading")
    sections = iter_heading_sections(normalized)

    return [
        [
            c.chunk_id
            for c in chunks
            if s <= c.metadata["char_start"] < e
        ]
        for s, e in sections
    ]


def main() -> None:
    qrels = []
    RAW.mkdir(parents=True, exist_ok=True)
    for p in RAW.glob("*.md"):
        p.unlink()

    for topic in TOPICS:
        core = topic["core"]
        md = build_md(core, topic["sections"])
        (RAW / f"{core}.md").write_text(md, encoding="utf-8")
        core_ids = section_chunk_ids(f"{core}.md", md)
        if len(core_ids) != len(topic["sections"]):
            raise RuntimeError(
                f"{core}：小节数 {len(topic['sections'])} 与归组数 {len(core_ids)} 不一致"
            )

        for dist_title, dist_sections in topic["distractors"]:
            dmd = build_md(dist_title, dist_sections)
            (RAW / f"{dist_title}.md").write_text(dmd, encoding="utf-8")

        for q in topic["queries"]:
            sec = q.get("answer_section")
            relevant = [] if sec is None else core_ids[sec]
            qrels.append(
                {
                    "query": q["query"],
                    "type": q.get("type", "direct"),
                    "relevant": relevant,
                }
            )

    EVAL.mkdir(parents=True, exist_ok=True)
    (EVAL / "qrels.json").write_text(
        json.dumps(qrels, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total_docs = sum(1 + len(t["distractors"]) for t in TOPICS)
    print(f"语料 {total_docs} 篇，query {len(qrels)} 条")


if __name__ == "__main__":
    main()
