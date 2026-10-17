"""程序化生成 data2 语料与评测集（机器学习领域，全新内容）。

用法：在项目根运行 `python scripts/generate_corpus2.py`。
产物：data2/raw/ 下 100 篇 .md（20 主题 × 5 篇：1 正 + 4 误导）；
      data2/eval/qrels.json 300 条手写 query（每主题 15 条，标注对应正文档）。
"""

import json
from pathlib import Path

from corpus_data3 import TOPICS_C
from corpus_data4 import TOPICS_D
from queries_data3 import QUERIES_C
from queries_data4 import QUERIES_D

TOPICS = TOPICS_C + TOPICS_D
QUERIES = {**QUERIES_C, **QUERIES_D}

RAW = Path("data2/raw")
EVAL = Path("data2/eval")


def distractor_content(title: str) -> str:
    """误导文档：标题与正文档共享领域词（提供干扰），内容为通用技术描述。"""
    return (
        f"# {title}\n\n"
        f"## 概念与背景\n\n"
        f"{title}是机器学习与数据工程中的一个重要话题，理解它的原理和适用场景，"
        f"才能在实践中正确运用。不同的问题和数据特点会导向不同的处理方式，"
        f"因此先厘清问题的本质，比记住具体方法更重要。\n\n"
        f"## 常见方法\n\n"
        f"针对{title}，业界积累了不少行之有效的做法。有的方法追求效果，"
        f"在精度上做到极致；有的方法追求效率，在成本和速度上更有优势。"
        f"选择时要结合数据规模、质量和业务目标，避免盲目套用所谓的标准做法。\n\n"
        f"## 常见误区\n\n"
        f"{title}的常见误区是只关注方法本身而忽视适用条件。很多技巧在特定前提下有效，"
        f"前提不成立时反而有害。忽视评估和验证，也会让人误判方法的真实效果。\n\n"
        f"## 与相关概念的关系\n\n"
        f"{title}与其他若干概念既有联系又有区别，混淆它们会导致方案选错。"
        f"理清边界，才能在该用它的时候用它、不该用的时候不误用。\n\n"
        f"## 实践要点\n\n"
        f"落地{title}时，建议先小范围验证，确认有效再推广。保留对照和评估，"
        f"任何改进都应以可量化的效果为依据，而非主观感觉。\n"
    )


def main() -> None:
    qrels = []
    RAW.mkdir(parents=True, exist_ok=True)
    for p in RAW.glob("*.md"):
        p.unlink()

    for topic in TOPICS:
        core = topic["core"]
        sections = "\n\n".join(f"## {h}\n\n{body}" for h, body in topic["sections"])
        (RAW / f"{core}.md").write_text(f"# {core}\n\n{sections}\n", encoding="utf-8")

        for d in topic["distractors"]:
            (RAW / f"{d}.md").write_text(distractor_content(d), encoding="utf-8")

        for q in QUERIES[core]:
            qrels.append({"query": q, "relevant": [f"{core}.md"]})

    EVAL.mkdir(parents=True, exist_ok=True)
    (EVAL / "qrels.json").write_text(
        json.dumps(qrels, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"data2 语料 {len(TOPICS) * 5} 篇，query {len(qrels)} 条")


if __name__ == "__main__":
    main()
