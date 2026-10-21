"""生成评测标注骨架：挑小节、填好 doc/section/start/end/type，query 留待填写。

为什么要有这一步
----------------
手工从 123 篇文档里挑 120 个待标注小节，既慢又容易漏。本脚本按配比自动挑好
候选（确定性，随机种子固定，可复现），把**除 query 文本之外的所有字段**都填好，
人工只需读小节、写问题、筛掉不合适的。

挑候选的规则
------------
- 只收 200~1500 字的小节：太短没内容可问，太长（整章）不好标；
- 五个技术栈轮转取样，避免某一栈占比过高；
- multi_block 取同一文档里相邻的两个小节（答案分散，逼模型做多块综合）；
- cross_doc 取不同技术栈里标题同词的小节对；
- no_answer 见 ``NO_ANSWER_QUERIES``，并在生成后**自动校验**关键词是否真的
  不在语料里（上一轮就栽在"标了 no_answer 但语料里其实有答案"上）。

用法
----
    python scripts/build_skeleton.py                    # 生成 120 条骨架
    python scripts/build_skeleton.py --out data/eval/qrels.skeleton.json
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

from ragkit.chunking import iter_heading_sections
from ragkit.text import clean_heading, tokenize_terms
from ragkit.text.normalize import normalize_text


def _ensure_utf8_stdout() -> None:
    """Windows 控制台默认 GBK，打印中文/符号会崩，强制 UTF-8。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

RAW = Path("data/raw")
# 只保留中文源：docker/docs 是纯英文，不符合"中文 RAG"的前提
STACKS = ["k8s", "tidb", "vue", "react"]

# 配比：direct 32.5% / paraphrase 32.5% / multi_block 15% / cross_doc 5% / no_answer 15%
# cross_doc 从 10% 降到 5%：跨文档"同主题"靠字面重叠判断并不可靠（会配出
# "Garbage collection" vs "metric collection"），所以改成人工指定 6 对。
QUOTA = {
    "direct": 39,
    "paraphrase": 39,
    "multi_block": 18,
    "cross_doc": 6,
    "no_answer": 18,
}

# 人工挑选的跨文档对比对（同一概念在两个技术栈里的不同实现）。
# 用 (文档关键词, 小节关键词) 模糊匹配，避免仓库路径变动导致精确匹配失败。
CROSS_DOC_PAIRS: list[tuple[tuple[str, str], tuple[str, str]]] = [
    (("lifecycle", "生命周期"), ("escape-hatches", "生命周期")),
    (("event-handling", "监听事件"), ("adding-interactivity", "响应事件")),
    (("conditional", "v-if"), ("conditional-rendering", "条件")),
    (("props", "单向数据流"), ("describing-the-ui", "Props")),
    (
        ("production-deployment", "生产环境"),
        ("build-a-react-app-from-scratch", "安装构建工具"),
    ),
    (("performance", "页面加载"), ("build-a-react-app-from-scratch", "应用程序模式")),
]

# 语料外的主题（k8s/docker/tidb/vue/react 五个技术栈之外的常见后端主题）。
# 选词原则：主题的**英文标识符**（Kafka / ZooKeeper / JVM ...）必须完全不在语料里，
# 否则检索器会因字面重叠把无关块排上来，这类 no_answer 太"弱"，测不出拒答。
NO_ANSWER_QUERIES = [
    "Kafka 出现消息积压时应该怎么处理？",
    "ZooKeeper 的选主机制是怎么工作的？",
    "HBase 的 RowKey 应该怎么设计才能避免热点？",
    "Flink 的水位线机制解决了什么问题？",
    "Cassandra 的一致性哈希是怎么实现的？",
    "HDFS 的副本机制如何保证数据可靠？",
    "Nginx 的负载均衡支持哪些算法？",
    "JVM 的垃圾回收器应该怎么选？",
    "TensorFlow 的分布式训练有哪几种策略？",
    "PyTorch 显存不足时可以怎么优化？",
    "RSA 签名的生成和验签流程是什么？",
    "ClickHouse 的 MergeTree 引擎是怎么组织数据的？",
    "RabbitMQ 的死信队列有什么作用？",
    "MongoDB 的副本集如何实现高可用？",
    "RocketMQ 的消息顺序怎么保证？",
    "Jenkins 的流水线脚本怎么写？",
    "Ansible 的 playbook 如何组织？",
    "Vagrant 的虚拟环境怎么管理？",
]


# 一个"中文小节"至少要有的中文字符数。
# 不用"中文字符占比"：Vue/React 的讲解小节常带大段示例代码，占比会被压到
# 0.05~0.2，但它们完全是有价值的中文内容；用绝对数量能准确区分
# 「中文讲解 + 代码」与「纯英文原文」。
_MIN_CHINESE_CHARS = 80


def _chinese_count(text: str) -> int:
    """中文字符数量。"""
    return sum(1 for char in text if "\u4e00" <= char <= "\u9fff")


def collect_sections() -> list[dict]:
    """收集所有文档的可标注**中文**小节（含字符区间）。

    跳过两种情况：① 标题为空（例如只有 Hugo shortcode 的行）；
    ② 中文字符数 < 80（k8s 中文站点里"英文原文 + 中文翻译"并存，
    英文小节对中文检索没有意义，不该进入标注）。
    """
    rows: list[dict] = []
    for stack in STACKS:
        for path in sorted((RAW / stack).glob("*.md")):
            rel = path.relative_to(RAW).as_posix()
            normalized = normalize_text(path.read_text(encoding="utf-8"))
            for index, (start, end) in enumerate(iter_heading_sections(normalized)):
                body = normalized[start:end]
                heading = clean_heading(body.splitlines()[0]) if body else ""
                if not heading or _chinese_count(body) < _MIN_CHINESE_CHARS:
                    continue
                rows.append(
                    {
                        "doc": rel,
                        "section": heading,
                        "start": start,
                        "end": end,
                        "chars": end - start,
                        "stack": stack,
                    }
                )
    return rows


def _pick_pool(rows: list[dict]) -> list[dict]:
    """可出题的候选池：长度 200~1500、标题非空、且不是纯代码块。"""
    pool = []
    for row in rows:
        if not (200 <= row["chars"] <= 1500):
            continue
        if not row["section"] or row["section"].startswith("```"):
            continue
        pool.append(row)
    return pool


def _by_stack(pool: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {stack: [] for stack in STACKS}
    for row in pool:
        grouped[row["stack"]].append(row)
    return grouped


def _round_robin(groups: dict[str, list[dict]], total: int) -> list[dict]:
    """按技术栈轮转取，保证各栈尽量均衡。"""
    picked: list[dict] = []
    cursors = {stack: 0 for stack in STACKS}
    while len(picked) < total:
        progressed = False
        for stack in STACKS:
            if len(picked) >= total:
                break
            bucket = groups[stack]
            if cursors[stack] < len(bucket):
                picked.append(bucket[cursors[stack]])
                cursors[stack] += 1
                progressed = True
        if not progressed:  # 候选不够，提前结束
            break
    return picked


# 命令参考型文档（Docker CLI 各命令）全是"操作步骤"碎片，相邻两节不构成
# "需要综合才能回答"的关系，不适合做 multi_block 题。
_REFERENCE_DOC_HINTS = ("__cli__", "reference", "commands", "__daemon__")
_ACTION_HEADINGS = (
    "use ", "set ", "start ", "stop ", "run ", "add ", "remove ", "create ",
    "enable ", "disable ", "verify ", "connect ", "configure ", "migrate ", "upgrade ",
)


def _is_reference_like(row: dict) -> bool:
    """判断小节是否属于"命令参考/操作步骤"类（不适合多块综合题）。"""
    if any(hint in row["doc"] for hint in _REFERENCE_DOC_HINTS):
        return True
    return row["section"].lower().startswith(_ACTION_HEADINGS)


def _multi_block_pairs(pool: list[dict], total: int) -> list[list[dict]]:
    """同一文档里相邻、都足够长、且不是命令参考的两个小节（答案分散）。"""
    by_doc: dict[str, list[dict]] = {}
    for row in pool:
        if not _is_reference_like(row):
            by_doc.setdefault(row["doc"], []).append(row)

    pairs: list[list[dict]] = []
    for doc in sorted(by_doc):
        sections = sorted(by_doc[doc], key=lambda r: r["start"])
        for first, second in zip(sections, sections[1:]):
            # 相邻（字符上连续）+ 两节都 ≥ 300 字：排除 Bash/Zsh 这类碎片小节
            if second["start"] - first["end"] <= 2 and min(
                first["chars"], second["chars"]
            ) >= 300:
                pairs.append([first, second])

    # 按技术栈轮转，避免 18 条全落在同一个源（如 React 的 learn 目录）
    by_stack: dict[str, list[list[dict]]] = {}
    for pair in pairs:
        by_stack.setdefault(pair[0]["stack"], []).append(pair)

    picked: list[list[dict]] = []
    cursors = {stack: 0 for stack in STACKS}
    while len(picked) < total:
        progressed = False
        for stack in STACKS:
            bucket = by_stack.get(stack, [])
            if cursors.get(stack, 0) < len(bucket) and len(picked) < total:
                picked.append(bucket[cursors[stack]])
                cursors[stack] = cursors.get(stack, 0) + 1
                progressed = True
        if not progressed:
            break
    return picked


# 配对时忽略的通用词：只共享这些词说明不了"同主题"
_STOPWORDS = {
    "using", "use", "used", "user", "the", "a", "an", "and", "or", "of", "for",
    "to", "in", "on", "with", "without", "by", "from", "how", "what", "when",
    "which", "set", "setup", "configure", "configuration", "config", "start",
    "stop", "run", "create", "add", "remove", "delete", "get", "list", "check",
    "使用", "设置", "配置", "如何", "怎么", "什么", "介绍", "概述", "说明", "管理",
}


def _topic_terms(heading: str) -> set[str]:
    """标题里的主题词：长度 ≥ 2 的实词，排除通用词。"""
    return {
        term
        for term in tokenize_terms(heading)
        if len(term) >= 2 and term.lower() not in _STOPWORDS
    }


def _find_section(pool: list[dict], doc_key: str, section_key: str) -> dict | None:
    """按关键词模糊匹配一个候选小节（文档路径含 doc_key、标题含 section_key）。"""
    for row in pool:
        if doc_key in row["doc"] and section_key.lower() in row["section"].lower():
            return row
    return None


def _cross_doc_pairs(pool: list[dict], total: int) -> list[list[dict]]:
    """按人工指定的清单配跨文档对比对；找不到的跳过并报告。"""
    pairs: list[list[dict]] = []
    missing: list[str] = []
    for (left_doc, left_sec), (right_doc, right_sec) in CROSS_DOC_PAIRS:
        left = _find_section(pool, left_doc, left_sec)
        right = _find_section(pool, right_doc, right_sec)
        if left is None or right is None:
            missing.append(f"{left_doc}/{left_sec} ↔ {right_doc}/{right_sec}")
            continue
        pairs.append([left, right])
    if missing:
        print(f"⚠️ {len(missing)} 对 cross_doc 未找到，已跳过：")
        for line in missing:
            print(f"   - {line}")
    return pairs[:total]


def _answer_entry(row: dict) -> dict:
    return {
        "doc": row["doc"],
        "section": row["section"],
        "start": row["start"],
        "end": row["end"],
    }


_ENGLISH_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.+#-]*")


def check_no_answer(queries: list[str]) -> tuple[list[str], list[str]]:
    """校验 no_answer query 的**英文标识符**是否真的不在语料里。

    只看专有名词（Kafka / JVM / RSA ...），不看"怎么/应该/机制"这类通用词——
    后者在任何语料里都必然出现，拿它当判据会把所有 no_answer 都误报一遍。

    Returns:
        tuple[list[str], list[str]]: (强 no_answer 列表, 需人工确认的说明列表)。
    """
    corpus_text = "\n".join(
        normalize_text(path.read_text(encoding="utf-8")) for path in RAW.rglob("*.md")
    )
    strong: list[str] = []
    weak: list[str] = []
    for query in queries:
        tokens = sorted(set(_ENGLISH_TOKEN.findall(query)))
        if not tokens:
            weak.append(f"{query} → 无英文标识符，无法自动判定")
            continue
        hit = [token for token in tokens if token in corpus_text]
        if hit:
            weak.append(f"{query} → 英文词出现在语料：{hit}")
        else:
            strong.append(query)
    return strong, weak


def main() -> None:
    """命令行入口。"""
    _ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="生成评测标注骨架")
    parser.add_argument(
        "--out", default="data/eval/qrels.skeleton.json", help="输出路径"
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子（可复现）")
    args = parser.parse_args()

    random.seed(args.seed)
    rows = collect_sections()
    pool = _pick_pool(rows)
    groups = _by_stack(pool)
    for stack in STACKS:
        random.shuffle(groups[stack])

    skeleton: list[dict] = []

    # direct / paraphrase 各半，共用轮转取样的池
    singles = _round_robin(groups, QUOTA["direct"] + QUOTA["paraphrase"])
    for i, row in enumerate(singles):
        qtype = "direct" if i < QUOTA["direct"] else "paraphrase"
        skeleton.append(
            {
                "query": "",  # 待填
                "type": qtype,
                "answers": [_answer_entry(row)],
                "_hint": {
                    "section_chars": row["chars"],
                    "section_preview": normalize_text(
                        (RAW / row["doc"]).read_text(encoding="utf-8")
                    )[row["start"] : row["end"]][:120],
                },
            }
        )

    for pair in _multi_block_pairs(pool, QUOTA["multi_block"]):
        skeleton.append(
            {
                "query": "",
                "type": "multi_block",
                "answers": [_answer_entry(row) for row in pair],
                "_hint": {"pair": [row["section"] for row in pair]},
            }
        )

    # cross_doc 是人工指定的，允许落在候选池之外（不受 200~1500 字限制）
    for pair in _cross_doc_pairs(rows, QUOTA["cross_doc"]):
        skeleton.append(
            {
                "query": "",
                "type": "cross_doc",
                "answers": [_answer_entry(row) for row in pair],
                "_hint": {"pair": [f"{r['stack']}/{r['section']}" for r in pair]},
            }
        )

    for query in NO_ANSWER_QUERIES:
        skeleton.append({"query": query, "type": "no_answer", "answers": []})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter

    counts = Counter(item["type"] for item in skeleton)
    print(f"已生成 {len(skeleton)} 条骨架 → {out}")
    for qtype, count in counts.items():
        print(f"  {qtype:<14}{count}")

    strong, weak = check_no_answer(NO_ANSWER_QUERIES)
    print(f"\nno_answer 校验：强 {len(strong)} 条 / 需人工确认 {len(weak)} 条")
    for line in weak:
        print(f"  ⚠️ {line}")


if __name__ == "__main__":
    main()
