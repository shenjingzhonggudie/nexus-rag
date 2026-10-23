# -*- coding: utf-8 -*-
"""无答案题独立查证：对每题用多组关键词/别名/正则搜全库，输出命中片段供人工判读。"""
import json, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = r"C:/Users/王佳浩/codex/2026-10-23/new-chat/outputs/rag-holdout"

corpus = {}
for line in open(ROOT + "/input/corpus.jsonl", encoding="utf-8"):
    o = json.loads(line); corpus[o["doc_id"]] = o["text"]
sections = {}
for line in open(ROOT + "/input/sections.jsonl", encoding="utf-8"):
    o = json.loads(line); sections.setdefault(o["doc_id"], []).append(o)

def sec_of(doc, pos):
    for s in sections.get(doc, []):
        if s["start"] <= pos < s["end"]:
            return s["section"] or "(全文)"
    return "?"

# 每题：若干 pattern（正则，忽略大小写），任一命中即打印上下文
QUERIES = {
 "h_0013 kubelet --node-status-update-frequency 默认秒数":
   [r"node[- ]status[- ]update[- ]frequency", r"状态更新频率", r"status[- ]update"],
 "h_0014 镜像GC HighThresholdPercent/LowThresholdPercent 默认值":
   [r"HighThresholdPercent", r"LowThresholdPercent", r"threshold"],
 "h_0015 kube-state-metrics 默认端口/路径":
   [r"kube[-_ ]state[-_ ]metrics", r":8080", r"/metrics", r"端口"],
 "h_0016 imageMaximumGCAge 默认值":
   [r"imageMaximumGCAge", r"imageMaximumGCAge|最大.*镜像.*时长", r"镜像.*默认.*（小时|分钟|秒）"],
 "h_0017 按优先级分阶段关闭默认每阶段秒数":
   [r"shutdownGracePeriodByPodPriority", r"默认.*优先级.*(秒|阶段)", r"priority.*默认"],
 "h_0032 tidb_idle_transaction_timeout 默认秒":
   [r"tidb_idle_transaction_timeout"],
 "h_0033 HikariCP minimumIdle 建议值":
   [r"minimumIdle", r"minimum[- ]?idle", r"最小空闲"],
 "h_0034 TiDB max_connections 默认":
   [r"max_connections", r"最大连接数", r"token[- ]limit", r"max[- ]?connections"],
 "h_0035 表达式索引配置开关名":
   [r"表达式索引", r"experimental.*expression", r"enable.*expression.*index", r"tidb_enable_expr"],
 "h_0036 Cursor Fetch FetchSize 建议值":
   [r"useCursorFetch", r"Cursor Fetch", r"cursor.*fetch", r"FetchSize"],
 "h_0050 KeepAlive max 默认值":
   [r"KeepAlive", r"max.*prop", r"最大缓存"],
 "h_0051 Suspense timeout 默认毫秒":
   [r"Suspense", r"suspense"],
 "h_0052 异步组件加载失败默认重试次数":
   [r"重试", r"retry", r"retires", r"load.*fail"],
 "h_0053 kebab-case 注册 → PascalCase 标签可用？":
   [r"kebab", r"Pascal", r"组件名", r"registration", r"大小写"],
 "h_0054 hydrateOnIdle 默认最大超时":
   [r"hydrateOnIdle", r"hydrate", r"闲置"],
 "h_0065 React 编译器最低 React 版本":
   [r"React 19", r"React 18", r"最低.*版本", r"minimum.*version", r"requires? React", r"版本要求"],
 "h_0066 Vite 无 Babel 配置时接入编译器":
   [r"Vite", r"vite", r"swc", r"Babel"],
 "h_0067 默认是否编译 node_modules":
   [r"node_modules", r"第三方库", r"third[- ]party"],
 "h_0068 监控采用进度怎么做":
   [r"监控.*采用|采用.*进度|adoption.*progress|monitor.*adoption", r"仪表|dashboard|telemetry|遥测"],
 "h_0069 CRA 迁移到新框架的步骤":
   [r"Create React App", r"CRA", r"迁移", r"migrat", r"eject"],
}

for qid_label, pats in QUERIES.items():
    print("=" * 100)
    print("◆", qid_label)
    seen = set()
    for pat in pats:
        try: rx = re.compile(pat, re.I)
        except re.error: continue
        for doc, text in corpus.items():
            for m in rx.finditer(text):
                p = m.start()
                key = (doc, p // 200)
                if key in seen: continue
                seen.add(key)
                a, b = max(0, p - 120), min(len(text), p + 180)
                snip = text[a:b].replace("\n", " ")
                print(f"  [{pat}] {doc} | {sec_of(doc,p)} @{p}: …{snip}…")
    if not seen:
        print("  （全库无命中）")
