"""候选题构建器。

职责：
    把四个技术栈的候选题数据（题干、答案小节、答案要点、最小支撑引文、无答案核验记录）
    编译成提交物：qrels.candidate.json、evidence.jsonl、pending.jsonl、challenges.jsonl。

边界：
    只读取输入语料与本地候选题数据；不调用被测系统，不读取 old_queries.jsonl。

承诺清单：
    1. 每条答案区间都来自 sections.jsonl，且经 loader.verify 校验坐标与小节标题。
    2. 每条最小支撑引文都必须在所属区间内被原文命中，否则构建失败（不静默跳过）。
    3. type 与 answers 数量匹配；no_answer 的 answers 恒为 []。
    4. 无答案题必须带缺失点与检索核验记录，且核验记录由本脚本对语料实检生成。
"""

from __future__ import annotations

import json
from pathlib import Path

import loader

OUT_DIR = Path(r"C:\Users\王佳浩\codex\2026-10-23\new-chat\outputs\rag-holdout\candidate")

import data_k8s  # noqa: E402
import data_react  # noqa: E402
import data_tidb  # noqa: E402
import data_vue  # noqa: E402

STACK_MODULES = [data_k8s, data_react, data_tidb, data_vue]

ALLOWED_TYPES = {"direct", "paraphrase", "multi_block", "cross_doc", "no_answer"}


class BuildError(Exception):
    """构建期校验失败。"""


def resolve(corpus: loader.Corpus, doc: str, section: str) -> loader.Section:
    """按文档与小节标题解析出区间。

    Args:
        corpus: 已加载语料。
        doc: 文档标识。
        section: 小节标题；空串表示整篇无标题文档。

    Returns:
        命中的 Section。

    Raises:
        BuildError: 文档不存在、标题不唯一或不存在。
    """
    if doc not in corpus.sections:
        raise BuildError(f"未知文档: {doc}")
    matched = [s for s in corpus.sections[doc] if s.section == section]
    if not matched:
        raise BuildError(f"{doc} 中没有小节标题 {section!r}")
    if len(matched) > 1:
        raise BuildError(f"{doc} 中小节标题 {section!r} 不唯一")
    return matched[0]


def locate_quote(corpus: loader.Corpus, sec: loader.Section, quote: str) -> tuple[int, int]:
    """在给定区间内定位引文，返回绝对起止偏移。

    Args:
        corpus: 已加载语料。
        sec: 所属区间。
        quote: 引文原文。

    Returns:
        (start, end) 绝对偏移，左闭右开。

    Raises:
        BuildError: 引文不在该区间内。
    """
    text = corpus.texts[sec.doc][sec.start:sec.end]
    idx = text.find(quote)
    if idx < 0:
        raise BuildError(f"引文不在 {sec.doc}[{sec.start},{sec.end}) 内: {quote[:60]!r}")
    return sec.start + idx, sec.start + idx + len(quote)


def build_items(corpus: loader.Corpus) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    """编译全部候选题。

    Args:
        corpus: 已加载语料。

    Returns:
        (qrels, evidence, others, problems)：
        qrels 为提交用标注数组；evidence 为全部有证据的题（含挑战题）；
        others 为 pending / challenge 记录；problems 为校验问题列表。

    Raises:
        BuildError: 数据结构不合法。
    """
    qrels: list[dict] = []
    evidence: list[dict] = []
    others: list[dict] = []
    problems: list[str] = []
    seen_ids: set[str] = set()

    for mod in STACK_MODULES:
        for item in mod.Q:
            qid = item["id"]
            if qid in seen_ids:
                problems.append(f"{qid}: id 重复")
            seen_ids.add(qid)

            qtype = item["type"]
            if qtype not in ALLOWED_TYPES:
                problems.append(f"{qid}: 未知 type {qtype}")

            answers: list[dict] = []
            for doc, section in item.get("answers", []):
                try:
                    sec = resolve(corpus, doc, section)
                except BuildError as exc:
                    problems.append(f"{qid}: {exc}")
                    continue
                answers.append({"doc": sec.doc, "section": sec.section,
                                "start": sec.start, "end": sec.end})

            points: list[dict] = []
            for p in item.get("points", []):
                if "doc" in p:
                    doc, section = p["doc"], p["section"]
                else:
                    doc, section = item["answers"][p.get("span", 0)]
                try:
                    sec = resolve(corpus, doc, section)
                    qs, qe = locate_quote(corpus, sec, p["quote"])
                except BuildError as exc:
                    problems.append(f"{qid}: {exc}")
                    continue
                points.append({
                    "point": p["point"],
                    "quote": p["quote"],
                    "doc": sec.doc,
                    "section": sec.section,
                    "start": sec.start,
                    "end": sec.end,
                    "quote_start": qs,
                    "quote_end": qe,
                })

            if qtype == "no_answer":
                if answers:
                    problems.append(f"{qid}: no_answer 的 answers 必须为空")
                verification = run_verification(corpus, item)
                ev = {
                    "id": qid,
                    "family_id": item.get("family_id", ""),
                    "subtype": item.get("subtype", ""),
                    "stack": item.get("stack", ""),
                    "set": "main",
                    "query": item["query"],
                    "type": qtype,
                    "answers": [],
                    "points": [],
                    "missing": item["missing"],
                    "verification": verification,
                }
                evidence.append(ev)
                qrels.append({"id": qid, "query": item["query"], "type": qtype,
                              "answers": [], "source": "holdout"})
                continue

            if qtype in ("direct", "paraphrase") and len(answers) != 1:
                problems.append(f"{qid}: {qtype} 需要恰好 1 个答案区间")
            if qtype in ("multi_block", "cross_doc") and not (2 <= len(answers) <= 3):
                problems.append(f"{qid}: {qtype} 需要 2~3 个答案区间")
            if qtype == "cross_doc" and len({a["doc"] for a in answers}) < 2:
                problems.append(f"{qid}: cross_doc 的区间必须来自不同文档")
            if item.get("set") == "challenge":
                others.append({
                    "id": qid,
                    "family_id": item.get("family_id", ""),
                    "subtype": item.get("subtype", ""),
                    "stack": item.get("stack", ""),
                    "kind": item.get("kind", "partial"),
                    "query": item["query"],
                    "answers": answers,
                    "supported": item.get("supported", []),
                    "unsupported": item.get("unsupported", []),
                    "correction": item.get("correction", ""),
                    "note": item.get("note", ""),
                })
                evidence.append({
                    "id": qid,
                    "family_id": item.get("family_id", ""),
                    "subtype": item.get("subtype", ""),
                    "stack": item.get("stack", ""),
                    "set": "challenge",
                    "query": item["query"],
                    "type": qtype,
                    "answers": answers,
                    "points": points,
                    "missing": item.get("missing"),
                    "verification": None,
                })
                continue

            evidence.append({
                "id": qid,
                "family_id": item.get("family_id", ""),
                "subtype": item.get("subtype", ""),
                "stack": item.get("stack", ""),
                "set": "main",
                "query": item["query"],
                "type": qtype,
                "answers": answers,
                "points": points,
                "missing": None,
                "verification": None,
            })
            qrels.append({"id": qid, "query": item["query"], "type": qtype,
                          "answers": answers, "source": "holdout"})

    for mod in STACK_MODULES:
        for item in mod.PENDING:
            others.append({
                "id": item["id"],
                "family_id": item.get("family_id", ""),
                "stack": item.get("stack", ""),
                "kind": "pending",
                "query": item["query"],
                "reason": item["reason"],
                "checked": run_verification(corpus, item),
            })

    problems.extend(loader.verify([(a["doc"], a["section"], a["start"], a["end"])
                                   for q in qrels for a in q["answers"]], corpus))
    return qrels, evidence, others, problems


def run_verification(corpus: loader.Corpus, item: dict) -> dict:
    """对无答案/待定题执行实检检索，生成核验记录。

    Args:
        corpus: 已加载语料。
        item: 候选题数据，需含 verify 字段（关键词/别名/文档范围）。

    Returns:
        含 keywords、scope、hit_count、nearest 的核验记录字典。
    """
    spec = item.get("verify", {})
    patterns = spec.get("patterns", [])
    stack = spec.get("stack")
    docs = spec.get("docs")
    nearest: list[dict] = []
    total = 0
    for pat in patterns:
        hits = corpus.find(pat, stack=stack, context=110, limit=6) if not docs else [
            h for d in docs for h in corpus.find(pat, doc=d, context=110, limit=6)
        ]
        total += len(hits)
        for h in hits:
            nearest.append({
                "pattern": pat,
                "doc": h["doc"],
                "section": h["section"],
                "start": h["sec_start"],
                "end": h["sec_end"],
                "snippet": h["snippet"].replace("\n", " ")[:300],
            })
    dedup: list[dict] = []
    keys: set[tuple] = set()
    for n in nearest:
        key = (n["doc"], n["section"], n["start"], n["snippet"][:60])
        if key in keys:
            continue
        keys.add(key)
        dedup.append(n)
    return {
        "keywords": spec.get("keywords", patterns),
        "aliases": spec.get("aliases", []),
        "scope": spec.get("scope", stack or "全库"),
        "docs_checked": docs or [],
        "hit_count": total,
        "nearest": dedup[:8],
        "cross_doc_check": spec.get("cross_doc_check", ""),
        "conclusion": spec.get("conclusion", ""),
    }


def main() -> None:
    """构建并写出全部提交物，打印统计与校验问题。

    Returns:
        None。
    """
    corpus = loader.load()
    qrels, evidence, others, problems = build_items(corpus)

    report = "\n".join(problems) if problems else "无问题：全部区间与引文校验通过。"
    (OUT_DIR / "build_problems.txt").write_text(report, encoding="utf-8")
    if problems:
        print("problems written to build_problems.txt:", len(problems))
        raise SystemExit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "qrels.candidate.json").write_text(
        json.dumps(qrels, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT_DIR / "evidence.jsonl").open("w", encoding="utf-8") as f:
        for row in evidence:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUT_DIR / "pending.jsonl").open("w", encoding="utf-8") as f:
        for row in others:
            if row.get("kind") == "pending":
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUT_DIR / "challenges.jsonl").open("w", encoding="utf-8") as f:
        for row in others:
            if row.get("kind") != "pending":
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    from collections import Counter
    print("qrels:", len(qrels), Counter(q["type"] for q in qrels))
    print("evidence:", len(evidence))
    print("challenges:", sum(1 for o in others if o.get("kind") != "pending"))
    print("pending:", sum(1 for o in others if o.get("kind") == "pending"))


if __name__ == "__main__":
    main()
