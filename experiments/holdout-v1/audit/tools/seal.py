# -*- coding: utf-8 -*-
"""独立审核封存脚本：生成 audit/review.jsonl 与 sealed/* 五件套。
审校依据：audit/answerable_intervals.txt（区间全文人工阅读）、audit/noanswer_search.txt（独立全库检索）、
audit/mech_report.json（机械校验）、去重比对（old_queries 二元组相似度、内部相似对、区间复用）。"""
import json, hashlib, sys, io, os, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = r"C:/Users/王佳浩/codex/2026-10-23/new-chat/outputs/rag-holdout"

corpus = {}
for line in open(ROOT + "/input/corpus.jsonl", encoding="utf-8"):
    o = json.loads(line); corpus[o["doc_id"]] = o["text"]

cands = json.load(open(ROOT + "/candidate/qrels.candidate.json", encoding="utf-8"))
ev = {}
for line in open(ROOT + "/candidate/evidence.jsonl", encoding="utf-8"):
    o = json.loads(line); ev[o["id"]] = o
chals = [json.loads(l) for l in open(ROOT + "/candidate/challenges.jsonl", encoding="utf-8")]
pend = [json.loads(l) for l in open(ROOT + "/candidate/pending.jsonl", encoding="utf-8")]

EXCLUDE = {"h_0038": "与开发题 q_0199『传给组件的 class 没在 props 里声明，最后会跑到哪去？』语义近重复（同一事实关系：未声明 class 透传落到根元素），按去重规则排除"}
REVISE = {"h_0022": "原标 multi_block 双区间；答案（v5.4 起空闲 28800 秒自动关闭、wait_timeout 控制）完整见于『连接池参数』区间，含 v5.4 前默认不关闭的对照。修订为 direct，仅保留 [212,4553)；第二区间与 h_0023/h_0024 重复且仅余补充信息"}

# ---- 每题审校理由 ----
R = {
"h_0001": "区间明示：每个 Node 在 kube-node-lease 有同名 Lease；心跳=对该 Lease 的 update，更新 spec.renewTime；控制面据时间戳判可用性。三证据点引文均在区间内。",
"h_0002": "cross_doc 成立：两种心跳形式及 .status 载体在 nodes.md『节点心跳』；心跳经 Lease API/update renewTime 传递的机制在 leases.md，综合方可完整回答『两种形式+各自载体』。",
"h_0003": "区间含原文：标记 Unknown 后等 5 分钟提交第一个驱逐请求；节点控制器每 5 秒检查节点状态。两问均被直接支撑。",
"h_0004": "区间『要求』小节列全：发行版启用 v2、内核 5.8+、运行时支持（containerd≥1.4/cri-o≥1.20）、systemd cgroup 驱动。",
"h_0005": "区间『路由控制器』明示：需读取 Node 对象的 get 权限（v1/Node: get）。",
"h_0006": "区间两处明示：对等 API 服务器无法响应时，源 API 服务器以 503 Service Unavailable 响应。",
"h_0007": "区间明示：DeviceClass/ResourceSlice 仅限管理员和 DRA 驱动访问；ResourceClaim 与 ResourceClaimTemplate API 作用范围均为命名空间。",
"h_0008": "区间原文：100 节点 DRA 规模测试中 kube-controller-manager QPS=75、Burst=150。",
"h_0009": "区间原文示例：shutdownGracePeriod=30s、CriticalPods=10s 时，前 20(30-10) 秒用于体面终止常规 Pod。",
"h_0010": "区间首句：每五分钟对未使用镜像 GC，每分钟对未使用容器 GC。",
"h_0011": "multi_block 两块均必要：containerLogMaxSize(默认10Mi)/containerLogMaxFiles(默认5) 在『Pod 和容器日志』；kubelet 日志 Linux 默认 journald（无 systemd 则 /var/log/*.log）、Windows 默认 C:\\var\\logs 在『系统组件日志』。",
"h_0012": "cross_doc 成立：Lease 的领导者选举角色在 leases.md『领导者选举』；两个开关（CoordinatedLeaderElection 特性门控 + coordination.k8s.io/v1beta1 API 组）在 coordinated-leader-election.md『启用协调领导者选举』。",
"h_0013": "无答案核验：nodes.md 仅描述 --node-status-update-frequency 的用途（@2895），全库无默认秒数；主题存在、具体点缺失，符合 FORMAT§7①。",
"h_0014": "无答案核验：HighThresholdPercent/LowThresholdPercent 仅见于 garbage-collection.md 且无数值；其余命中（--unhealthy-zone-threshold 等）与题无关。",
"h_0015": "无答案核验：kube-state-metrics.md 全文只说『公开一个 HTTP 端点』，无端口与路径；observability.md 的 /metrics* 路径属 kubelet 而非 kube-state-metrics。",
"h_0016": "无答案核验：imageMaximumGCAge 仅见字段说明与示例值 12h45m，无默认值。",
"h_0017": "无答案核验：shutdownGracePeriodByPodPriority 仅出现示例配置（10/180/120/60 秒），非默认值；语料未给任何默认分阶段时长。",
"h_0056": "区间明示：遇到疑似违反 React 规则的代码时安全跳过优化而非冒险改变行为。",
"h_0057": "区间明示：第一步用 \"use no memo\" 临时禁用编译确认关联；修复后移除并在 React DevTools 验证 ✨ 徽章。",
"h_0058": "cross_doc 成立：\"use memo\"（annotation 模式选择加入）在 incremental-adoption.md；\"use no memo\"（排除组件/调试）在 debugging.md，各自场景明示。与 h_0057 共用调试区间但测点为指令对，非同事实套壳。",
"h_0059": "区间明示：Babel overrides 选项可对不同目录应用不同插件，适合按目录逐批接入。",
"h_0060": "区间明示：gating 选项 + 工作原理（优化代码外裹运行时检查，开关 true 走优化版）。",
"h_0061": "区间明示：不，Create React App 已不建议使用（sunsetting 博客链接）。",
"h_0062": "区间明示：Next.js (App Router)、React Router (v7)、Expo；支持 CSR/SPA/SSG，可部署 CDN/静态托管，无需服务器。",
"h_0063": "区间明示：务必启用 eslint-plugin-react-hooks 规则。",
"h_0064": "区间明示：Vite、Parcel、Rsbuild（Metro 仅 React Native 场景，文中明确建议从前三者开始）。",
"h_0065": "无答案核验：react-compiler 三篇（index/incremental-adoption/debugging）均无最低版本；index.md 仅链接『包含 React 版本兼容性』的参考页。",
"h_0066": "无答案核验：编译器文档仅覆盖 Babel 插件接入；Vite 命中均在无关文档（构建工具介绍、生产部署等），无 Vite+编译器接入说明。",
"h_0067": "无答案核验：全库无 node_modules/第三方库编译范围讨论。",
"h_0068": "无答案核验：『监控你的采用进度』仅出现在文档开头目录列表，正文无对应小节；正文仅有 A/B 测试动机性描述，无具体做法。主题存在、具体点缺失。",
"h_0069": "无答案核验：语料仅说 CRA 已淘汰并链接博客，各处迁移字样均与 CRA→框架迁移步骤无关。",
"h_0021": "区间明示：经验公式 connections=((core_count*2)+effective_spindle_count)；core_count 为物理核心数、不含超线程。",
"h_0023": "区间明示：useServerPrepStmts=true（默认 false）+ cachePrepStmts=true 才能在服务端执行并复用预处理语句。",
"h_0024": "区间明示：rewriteBatchedStatements 下 insert 仅纯 values 拼接可合并，含其他差异（如 ON DUPLICATE KEY UPDATE 直写）不可；批量更新 ≥3 处改写为 multiple-queries。",
"h_0025": "区间明示：组合索引需满足最左前缀，仅按 published_at 过滤无法使用 (title, published_at) 组合索引。",
"h_0026": "区间明示：索引列上做函数计算致优化器无法使用索引；两种改写：范围条件改写、建 YEAR() 表达式索引。",
"h_0027": "multi_block 两块均必要：覆盖索引定义在『创建索引』；写法（索引列包含查询列、避免 SELECT *）及回表说明在『使用索引』。",
"h_0028": "区间明示：IN 匹配值建议 ≤300；用不上索引的写法：!=/NOT IN、LIKE 前导 %（参考答案需并列给出）。",
"h_0029": "区间明示：每增一个索引多一个 Key-Value→写入越慢、空间越大，且影响优化器运行时间、不合适索引误导优化器。",
"h_0030": "cross_doc 成立：varchar 主键 + 数值常量→隐式类型转换→索引失效案例与执行计划（Cast→TableFullScan）在 implicit-type-conversion 文档；『索引列上做类型转换致优化器无法使用索引』的通用原则在 index-best-practice，归因需综合。",
"h_0031": "multi_block 两块均必要：唯一索引 uk_、普通索引 idx_ 前缀在『索引命名规范』；字段名≤30 字符、字段数≤60 在『字段命名规范』。",
"h_0032": "无答案核验：tidb_idle_transaction_timeout 仅见 v7.6.0 引入与用途，无默认秒数。",
"h_0033": "无答案核验：minimumIdle 仅描述作用（按业务配置），无数值。",
"h_0034": "无答案核验：max_connections 全库零命中；『最大连接数』命中均属连接池参数（maximumPoolSize），非服务端上限。",
"h_0035": "无答案核验：语料仅说『需在 TiDB 配置文件中开启表达式索引特性』，未给出开关名。",
"h_0036": "无答案核验：Cursor Fetch 仅要求 FetchSize 为正整数并配 useCursorFetch=true，无建议数值。",
"h_0039": "区间明示：多根节点无自动透传，未显式绑定 $attrs 抛运行时警告；避免方式为在目标根元素显式 v-bind=\"$attrs\"。",
"h_0040": "区间明示：attrs 非响应式，不能侦听；替代：用 prop 或 onUpdated 结合最新 attrs 执行副作用。",
"h_0041": "区间明示：组件事件无冒泡，只能监听直接子组件；跨多层用外部事件总线或全局状态管理。",
"h_0042": "区间 tip 明示：原生事件名 click 写入 emits 后，监听器只响应组件触发的 click，不再响应原生 click。",
"h_0044": "区间明示：delay 默认 200ms（加载组件显示前延迟）；timeout 默认 Infinity。",
"h_0045": "区间明示：初次渲染无异步依赖直接进入完成状态；完成后更深层新的异步依赖不会使其回退挂起。",
"h_0046": "cross_doc 成立：suspensible 默认 true 时自身加载/报错/延时/超时选项被忽略、suspensible:false 自管（suspense.md『异步组件』）；async.md 提供这些选项的默认值语境。",
"h_0047": "区间明示：include/exclude 按组件 name 选项匹配；3.2.34+ script setup SFC 自动按文件名生成 name。",
"h_0048": "区间明示：指定 max 后行为类似 LRU，超限销毁最久未访问的缓存实例。",
"h_0049": "区间明示：钩子须同步注册，setTimeout 回调中实例已丢失不工作；同步调用栈且最终源自 setup 的外部函数可调用。",
"h_0050": "无答案核验：keep-alive 文档仅给出 max 的 LRU 行为，未给默认值；全库无『不传 max 默认缓存数』表述。",
"h_0051": "无答案核验：Suspense 的 timeout prop 仅说可配置（0 表示立即显示后备），无默认毫秒；async.md 的 Infinity 属 defineAsyncComponent 而非 Suspense。",
"h_0052": "无答案核验：vue 文档（async.md 全文）无异步组件失败重试机制与次数；『重试』命中均在 tidb 事务文档。",
"h_0053": "无答案核验：registration.md『组件名格式』仅给出 PascalCase 注册→模板可用 <PascalCase>/<my-component> 的方向；反向（kebab-case 注册→PascalCase 标签）未覆盖，DOM 内模板注意事项目亦不含此结论。",
"h_0054": "无答案核验：hydrateOnIdle 仅注明『传递可选的最大超时』，无默认数值。",
}

# challenges 理由
RC = {
"h_0018": "纠错核验通过：区间明示 shutdownGracePeriodCriticalPods 应小于 shutdownGracePeriod，且两者默认 0；20s/30s 配法违反约束，语料可纠正。",
"h_0070": "纠错核验通过：区间明示编译错误罕见、构建中断『很可能是编译器中的一个 bug』应上报；『多半是代码违规』前提不成立，可纠正。",
"h_0037": "纠错核验通过：区间明示 max_execution_time 仅适用于所有 SELECT 语句（含 FOR UPDATE），默认 0；对写入/DDL 是否生效无依据，前提可纠正。",
"h_0055": "纠错核验通过：区间明示多根节点组件没有自动 attribute 透传行为；class 不会自动落到 main，前提可纠正。",
}

RP = {
"h_0019": "待定维持：leaseDurationSeconds 数值 3600 仅出现于 kube-apiserver 身份租约 YAML 示例，对象不同不能外推；coordinated-leader-election.md 只给字段语义与续约节奏，无节点心跳租约默认时长。审核独立检索确认相同结论。",
"h_0020": "待定维持：节点控制器侧『Unknown 后 5 分钟提交首个驱逐请求』在语料内，但 Pod 侧默认容忍时长（tolerationSeconds）及区域健康比例、速率限制对实际驱逐时间的复合影响无法由语料推出唯一数值。",
}

# ---- 重新机械校验 challenges（复用 mech 逻辑）----
secs = {}
for line in open(ROOT + "/input/sections.jsonl", encoding="utf-8"):
    o = json.loads(line); secs.setdefault(o["doc_id"], []).append(o)
def check_entry(e):
    probs = []
    for a in e.get("answers", []):
        d, s0, e0 = a["doc"], a["start"], a["end"]
        if d not in corpus: probs.append("doc 缺失"); continue
        t = corpus[d]
        if not (0 <= s0 < e0 <= len(t)): probs.append("区间越界"); continue
        if not t[s0:e0].startswith("##"): probs.append("未以##开头")
        ok = any(x.get("doc_id") == d and x["start"] == s0 and x["end"] == e0 and x["section"] == a["section"] for x in secs.get(d, []))
        if not ok: probs.append("sections 不匹配")
    return probs
chal_probs = {e["id"]: check_entry(e) for e in chals}
assert not any(chal_probs.values()), chal_probs

# ---- 生成 sealed/qrels.test.json ----
main, excluded_ids = [], set(EXCLUDE)
for c in cands:
    if c["id"] in excluded_ids: continue
    if c["id"] in REVISE and c["id"] == "h_0022":
        c = dict(c); c["type"] = "direct"
        c["answers"] = [a for a in c["answers"] if a["section"] == "连接池参数"]
    main.append(c)

# 终检：类型/数量匹配
for c in main:
    n = len(c["answers"])
    if c["type"] in ("direct", "paraphrase"): assert n == 1, c["id"]
    elif c["type"] == "no_answer": assert n == 0, c["id"]
    else: assert 2 <= n <= 3, c["id"]
ids = [c["id"] for c in main]
assert len(ids) == len(set(ids))

# ---- 生成 sealed/metadata.jsonl ----
def meta_row(c, setname):
    e = ev.get(c["id"], {})
    row = {
        "id": c["id"],
        "set": setname,
        "category": c["type"],
        "subtype": e.get("subtype", ""),
        "family_id": e.get("family_id", ""),
        "stack": (c["answers"][0]["doc"].split("/")[0] if c["answers"] else "react"),
    }
    note = R.get(c["id"]) or REVISE.get(c["id"], "")
    row["evidence_note"] = note
    return row

meta = [meta_row(c, "main") for c in main]
for e in chals:
    row = {
        "id": e["id"], "set": "challenges", "category": "no_answer_binary",
        "subtype": e.get("subtype", ""), "family_id": e.get("family_id", ""),
        "stack": e["answers"][0]["doc"].split("/")[0],
        "key_points": e.get("supported", []),
        "evidence_note": RC[e["id"]],
        "correction": e.get("correction", ""),
        "note": e.get("note", ""),
    }
    meta.append(row)

# family 交叉标注（同族/相邻事实，用于后续防泄漏审阅）
CROSS = {
    "h_0001": ["h_0002"], "h_0002": ["h_0001", "h_0012"],
    "h_0057": ["h_0058"], "h_0058": ["h_0057"],
    "h_0044": ["h_0046"], "h_0046": ["h_0044", "h_0045"],
    "h_0009": ["challenges:h_0018"], "h_0018": ["h_0009"],
    "h_0050": ["old:q_0227", "old:q_0066"], "h_0048": ["old:q_0227", "old:q_0066"],
    "h_0014": ["old:q_0234"], "h_0021": ["h_0033"], "h_0033": ["h_0021"],
    "h_0022": ["h_0023", "h_0024"], "h_0025": ["h_0026", "h_0028"],
    "h_0039": ["challenges:h_0055"], "h_0055": ["h_0039"],
}
for row in meta:
    if row["id"] in CROSS:
        row["cross_refs"] = CROSS[row["id"]]

# ---- 生成 sealed/challenges.jsonl ----
sealed_chals = []
for e in chals:
    e2 = dict(e); e2["audit"] = {"verdict": "通过", "note": RC[e["id"]]}
    sealed_chals.append(e2)

# ---- 写文件 ----
def dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(obj, list) and path.endswith(".jsonl"):
            for r in obj: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)

os.makedirs(ROOT + "/sealed", exist_ok=True)
dump(ROOT + "/sealed/qrels.test.json", main)
dump(ROOT + "/sealed/metadata.jsonl", meta)
dump(ROOT + "/sealed/challenges.jsonl", sealed_chals)

# ---- review.jsonl ----
review = []
for c in cands:
    qid = c["id"]
    e = ev.get(qid, {})
    if qid in EXCLUDE:
        review.append({"id": qid, "verdict": "排除", "type": c["type"], "query": c["query"],
                       "reason": EXCLUDE[qid],
                       "scope": "与 248 条开发题做规范化二元组相似度比对（阈值 0.25，人工复核全部 ≥0.25 对）"})
        continue
    if qid in REVISE:
        review.append({"id": qid, "verdict": "修订", "type_after": "direct", "type_before": c["type"],
                       "query": c["query"], "reason": REVISE[qid],
                       "quotes_verified": len(e.get("points", [])),
                       "scope": "区间全文人工阅读 + 引文坐标复核 + 跨题区间复用分析"})
        continue
    if c["type"] == "no_answer":
        review.append({"id": qid, "verdict": "通过", "type": c["type"], "query": c["query"],
                       "reason": R[qid],
                       "scope": "独立关键词/别名/正则全库检索（100 篇文档），人工复核全部命中片段；未采信被测系统任何输出"})
        continue
    review.append({"id": qid, "verdict": "通过", "type": c["type"], "query": c["query"],
                   "reason": R[qid],
                   "quotes_verified": len(e.get("points", [])),
                   "scope": "text[start:end] 全文人工阅读；引文与坐标子串校验；小节/文档/越界校验"})
for e in chals:
    review.append({"id": e["id"], "verdict": "通过", "type": "no_answer_binary(纠错)", "query": e["query"],
                   "reason": RC[e["id"]], "scope": "区间全文阅读 + 前提可纠正性核验 + 机械校验（区间/小节）"})
for p in pend:
    review.append({"id": p["id"], "verdict": "待定", "type": "pending", "query": p["query"],
                   "reason": RP[p["id"]],
                   "scope": "复现作者检索路径并独立扩展别名检索；确认证据不足且非易确认"})
dump(ROOT + "/audit/review.jsonl", review)

# ---- manifest.json ----
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(65536), b""): h.update(blk)
    return h.hexdigest()

from collections import Counter
tc = Counter(c["type"] for c in main)
now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
manifest = {
  "version": "1.0.0",
  "sealed_at": now,
  "dataset": "rag-holdout",
  "counts": {
    "main": len(main),
    "main_by_type": dict(sorted(tc.items())),
    "challenges": len(sealed_chals),
    "pending": len(pend),
    "excluded": len(excluded_ids),
  },
  "files": {
    "sealed/qrels.test.json": sha(ROOT + "/sealed/qrels.test.json"),
    "sealed/metadata.jsonl": sha(ROOT + "/sealed/metadata.jsonl"),
    "sealed/challenges.jsonl": sha(ROOT + "/sealed/challenges.jsonl"),
    "input/corpus.jsonl": sha(ROOT + "/input/corpus.jsonl"),
    "input/sections.jsonl": sha(ROOT + "/input/sections.jsonl"),
    "input/old_queries.jsonl": sha(ROOT + "/input/old_queries.jsonl"),
    "input/corpus_manifest.json": sha(ROOT + "/input/corpus_manifest.json"),
  },
  "corpus_docs": len(corpus),
  "revision_log": [
    {"at": now, "id": "h_0022", "change": "type multi_block→direct；answers 收敛为『连接池参数』[212,4553)",
     "reason": REVISE["h_0022"], "by": "独立审核"},
    {"at": now, "id": "h_0038", "change": "从主集排除", "reason": EXCLUDE["h_0038"], "by": "独立审核"},
  ],
  "eval_protocol": {
    "answerable_false_rejection_rate": "可回答题（direct/paraphrase/multi_block/cross_doc，n=42）中被系统整体拒答的比例；越低越好",
    "no_answer_refusal": "按类别统计正确拒答数/总数（含困难无答案子类：主题在语料中存在但所问具体点缺失，如 h_0013/h_0035/h_0053/h_0068）",
    "answerable_retrieval": "recall@5 与 MRR，块级命中=检索片段与任一标注区间同文档且存在重叠；k=5",
    "caveat": "区间/块命中率只衡量检索层面，不得解释为最终回答正确率；最终回答正确率需人工检查返回证据是否充分",
    "human_verification_subset": ["h_0003", "h_0011", "h_0013", "h_0021", "h_0030", "h_0032",
                                   "h_0044", "h_0046", "h_0053", "h_0059", "h_0062", "h_0068"],
    "human_subset_note": "验收前固定，按栈×类型分层，含 3 条困难无答案；不看系统表现挑选",
    "integrity": "审核不参考系统表现；封存后修订须保留 revision_log 并递增版本号",
  },
}
dump(ROOT + "/sealed/manifest.json", manifest)

print("主集", len(main), "类分布", dict(sorted(tc.items())))
print("challenges", len(sealed_chals), "pending", len(pend), "excluded", list(EXCLUDE))
print("metadata 行数", len(meta))
