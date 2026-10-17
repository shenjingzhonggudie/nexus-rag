"""程序化生成语料与评测集：从 corpus_data / corpus_data2 的知识库批量生成。

用法：在项目根运行 `python scripts/generate_corpus.py`。
产物：data/raw/ 下 100 篇 .md（20 主题 × 5 篇：1 正 + 4 误导）；
      data/eval/qrels.json 300 条 query（每主题 15 条，标注对应正文档）。
"""

import json
from pathlib import Path

from corpus_data import TOPICS_A
from corpus_data2 import TOPICS_B
from queries_data import QUERIES_A
from queries_data2 import QUERIES_B

TOPICS = TOPICS_A + TOPICS_B
QUERIES = {**QUERIES_A, **QUERIES_B}

RAW = Path("data/raw")
EVAL = Path("data/eval")


def distractor_content(title: str) -> str:
    """误导文档：标题与正文档共享大类词（提供干扰），内容为充实的通用技术描述。"""
    return (
        f"# {title}\n\n"
        f"## 定位与背景\n\n"
        f"{title}是系统设计中需要认真对待的一个课题，面向生产环境里真实存在的需求。"
        f"理解它的来龙去脉，才能在合适的场景正确使用。不同团队在业务规模和资源约束下，"
        f"对同一个课题的处理方式可能有很大差异，因此先厘清适用边界比记住具体做法更重要。\n\n"
        f"## 关键考量\n\n"
        f"实施{title}时，性能、可靠性、可维护性三个维度都要权衡。性能决定了系统在高负载下的表现，"
        f"可靠性决定了故障发生时的可用性，可维护性决定了长期演进的成本。三者往往相互制约，"
        f"没有放之四海皆准的标准答案，需要结合具体场景做出取舍。\n\n"
        f"## 常见实现方式\n\n"
        f"{title}在实践中存在多种实现路径。有的方案追求极致性能，用更底层的手段换取吞吐；"
        f"有的方案追求简单可靠，牺牲部分性能换取可维护性。选择时应当先明确约束条件，"
        f"再在候选方案中做权衡，避免盲目追求所谓的行业最佳实践。\n\n"
        f"## 异常与边界\n\n"
        f"{title}最容易被忽视的是异常场景。只考虑正常流程、不考虑失败和边界条件，"
        f"上线后往往会付出更高的代价。完善的监控和日志是发现问题的前提，"
        f"健全的降级与兜底策略是问题发生时最后的防线。\n\n"
        f"## 实践建议\n\n"
        f"落地{title}时，建议小步迭代、灰度验证，先用可控的范围验证方案的正确性，"
        f"再逐步扩大。同时保留回滚能力，任何优化都不应以牺牲可观测性和回退能力为代价。\n"
    )


def main() -> None:
    qrels = []
    # 清空旧语料，重新生成
    for p in RAW.glob("*.md"):
        p.unlink()

    for topic in TOPICS:
        core = topic["core"]
        sections = "\n\n".join(f"## {h}\n\n{body}" for h, body in topic["sections"])
        (RAW / f"{core}.md").write_text(f"# {core}\n\n{sections}\n", encoding="utf-8")

        for d in topic["distractors"]:
            (RAW / f"{d}.md").write_text(distractor_content(d), encoding="utf-8")

        # 每条 query 从手写自然语言列表读取（不再用"概念词 × 模板"合成）
        for q in QUERIES[core]:
            qrels.append({"query": q, "relevant": [f"{core}.md"]})

    EVAL.mkdir(parents=True, exist_ok=True)
    (EVAL / "qrels.json").write_text(
        json.dumps(qrels, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"语料 {len(TOPICS) * 5} 篇，query {len(qrels)} 条")


if __name__ == "__main__":
    main()
