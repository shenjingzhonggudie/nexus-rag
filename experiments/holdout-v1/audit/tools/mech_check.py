# -*- coding: utf-8 -*-
"""独立审核者：机械校验（不读被测系统任何实现/配置/输出）。

检查项：
  A. id 唯一
  B. type 合法且与 answers 数量匹配；no_answer 必须 []
  C. doc 与 corpus.jsonl doc_id 逐字符一致
  D. 区间合法 0<=start<end<=len(text)
  E. section 与 sections.jsonl 中覆盖 [start,end) 的小节一致（含 2 篇无标题文档 section==""）
  F. text[start:end] 以 '##' 标题行开头（无标题文档除外）
  G. evidence.jsonl 的 quote 必须是 doc_text[quote_start:quote_end] 原样子串，
     且 quote 落在标注区间 [start,end) 内
"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = r"C:/Users/王佳浩/codex/2026-10-23/new-chat/outputs/rag-holdout"

corpus = {}
with open(ROOT + "/input/corpus.jsonl", encoding="utf-8") as f:
    for line in f:
        o = json.loads(line)
        corpus[o["doc_id"]] = o["text"]

sections = {}
with open(ROOT + "/input/sections.jsonl", encoding="utf-8") as f:
    for line in f:
        o = json.loads(line)
        sections.setdefault(o["doc_id"], []).append(o)

cands = json.load(open(ROOT + "/candidate/qrels.candidate.json", encoding="utf-8"))

evidence = {}
with open(ROOT + "/candidate/evidence.jsonl", encoding="utf-8") as f:
    for line in f:
        o = json.loads(line)
        evidence[o["id"]] = o

ALLOWED = {"direct": 1, "paraphrase": 1, "multi_block": (2, 3), "cross_doc": (2, 3), "no_answer": 0}
ids = [c["id"] for c in cands]
report = []

# A. id 唯一
dup = {i for i in ids if ids.count(i) > 1}
print(f"A. 题量={len(ids)} 唯一id={len(set(ids))} 重复={sorted(dup) if dup else '无'}")

def locate_section(doc_id, start, end):
    """返回覆盖区间起点的小节记录；按 sections.jsonl 的 [start,end) 匹配。"""
    for s in sections.get(doc_id, []):
        if s["start"] == start and s["end"] == end:
            return s, "exact"
    # 容差：小节边界一致才允许；否则报告不匹配
    for s in sections.get(doc_id, []):
        if s["start"] <= start and end <= s["end"]:
            return s, "inside"
    return None, "none"

for c in cands:
    qid, typ, ans = c["id"], c["type"], c["answers"]
    probs = []
    # B
    if typ not in ALLOWED:
        probs.append(f"type 非法: {typ}")
    else:
        n = len(ans)
        want = ALLOWED[typ]
        if typ in ("direct", "paraphrase"):
            if n != 1: probs.append(f"{typ} 应恰 1 个 answers, 实际 {n}")
        elif typ == "no_answer":
            if n != 0: probs.append(f"no_answer 应 [], 实际 {n} 个")
        else:
            if not (want[0] <= n <= want[1]): probs.append(f"{typ} 应 2~3 个, 实际 {n}")
    # C/D/E/F
    for a in ans:
        doc = a["doc"]; s0, e0 = a["start"], a["end"]
        if doc not in corpus:
            probs.append(f"doc 不在 corpus: {doc}"); continue
        text = corpus[doc]
        if not (0 <= s0 < e0 <= len(text)):
            probs.append(f"区间越界: {s0},{e0}, len={len(text)}"); continue
        seg, how = locate_section(doc, s0, e0)
        if seg is None:
            probs.append(f"区间不匹配任何 sections 小节: {s0},{e0}")
        else:
            if seg["section"] != a["section"]:
                probs.append(f"section 不一致: 标注='{a['section']}' sections='{seg['section']}' ({how})")
        if not text[s0:e0].startswith("##"):
            head = text[s0:s0+30].replace("\n", "\\n")
            probs.append(f"区间未以 '##' 开头: '{head}'")
    # G. 引文子串校验
    ev = evidence.get(qid)
    if typ != "no_answer" and ev is None:
        probs.append("evidence.jsonl 缺该题")
    if ev:
        for p in ev.get("points", []):
            pd, qs, qe = p["doc"], p["quote_start"], p["quote_end"]
            if pd not in corpus:
                probs.append(f"evidence doc 不在 corpus: {pd}"); continue
            t = corpus[pd]
            if t[qs:qe] != p["quote"]:
                probs.append(f"引文与坐标不符: [{qs},{qe}) '{p['quote'][:30]}...'")
            # 引文须落在标注的对应 answers 区间内
            hit = any(a["doc"] == pd and a["start"] <= qs and qe <= a["end"] for a in ans)
            if not hit:
                probs.append(f"引文 [{qs},{qe}) 不在任何标注区间内")
    report.append({"id": qid, "problems": probs})

bad = [r for r in report if r["problems"]]
print(f"共 {len(cands)} 题，机械校验存在问题 {len(bad)} 题：")
for r in bad:
    print(" ", r["id"], "|", "; ".join(r["problems"]))

json.dump(report, open(ROOT + "/audit/mech_report.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("已写 audit/mech_report.json")
