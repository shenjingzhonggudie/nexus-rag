"""无答案候选的“检索核验”工具。

职责：
    对每条无答案候选，按给定的关键词、别名与文档范围在固定语料中做穷尽式检索，
    打印命中的文档、小节与上下文，供人工判断“语料是否真的缺少所需信息”。

边界：
    只处理输入语料；不调用被测系统；不读取 old_queries.jsonl。

承诺清单：
    1. 检索范围覆盖 corpus.jsonl 全部文档（除非显式限定 stack/doc）。
    2. 每条候选同时检索中文关键词、英文术语、常见别名与可能的数值写法。
    3. 输出即核验记录：命中列表为空是“判为无答案”的必要条件，不是充分条件。
"""

from __future__ import annotations

import sys

import loader

CASES: list[dict] = [
    {
        "key": "k8s-node-status-update-frequency-default",
        "patterns": [r"node-status-update-frequency", r"节点状态.{0,10}频率", r"上报频率"],
        "stack": "k8s",
    },
    {
        "key": "k8s-image-gc-threshold-default",
        "patterns": [r"HighThresholdPercent", r"LowThresholdPercent", r"阈值.{0,10}百分比"],
        "stack": "k8s",
    },
    {
        "key": "k8s-ksm-endpoint-port",
        "patterns": [r"kube-state-metrics", r"HTTP 端点", r":\d{4,5}/metrics", r"端口"],
        "stack": "k8s",
    },
    {
        "key": "k8s-cni-plugin-names",
        "patterns": [r"CNI", r"网络插件", r"Calico|Flannel|Cilium|Weave"],
        "stack": "k8s",
    },
    {
        "key": "k8s-node-lease-duration",
        "patterns": [r"leaseDurationSeconds", r"租约时长", r"节点心跳.{0,30}秒", r"nodeLeaseDurationSeconds"],
        "stack": "k8s",
    },
    {
        "key": "react-compiler-min-react-version",
        "patterns": [r"React 版本兼容性", r"最低.{0,6}版本", r"React \d+\.\d+", r"支持.{0,10}React 版本"],
        "stack": "react",
    },
    {
        "key": "react-compiler-vite-config",
        "patterns": [r"Vite", r"vite\.config", r"babel-plugin-react-compiler"],
        "stack": "react",
    },
    {
        "key": "react-compiler-node-modules",
        "patterns": [r"node_modules", r"编译库", r"预编译的库", r"第三方库"],
        "stack": "react",
    },
    {
        "key": "react-eslint-rule-names",
        "patterns": [r"eslint-plugin-react-hooks", r"rules-of-hooks", r"exhaustive-deps", r"ESLint 规则"],
        "stack": "react",
    },
    {
        "key": "react-cra-migration-steps",
        "patterns": [r"Create React App", r"迁移", r"Sunsetting"],
        "stack": "react",
    },
    {
        "key": "tidb-idle-transaction-timeout-default",
        "patterns": [r"tidb_idle_transaction_timeout", r"事务.{0,6}空闲超时"],
        "stack": "tidb",
    },
    {
        "key": "tidb-minimum-idle-value",
        "patterns": [r"minimumIdle", r"最小空闲连接"],
        "stack": "tidb",
    },
    {
        "key": "tidb-max-connections",
        "patterns": [r"max_connections", r"最大连接数", r"连接数上限"],
        "stack": "tidb",
    },
    {
        "key": "tidb-expression-index-switch",
        "patterns": [r"表达式索引", r"tidb_enable", r"实验特性"],
        "stack": "tidb",
    },
    {
        "key": "tidb-cursor-fetch-size",
        "patterns": [r"useCursorFetch", r"FetchSize", r"Cursor Fetch"],
        "stack": "tidb",
    },
    {
        "key": "vue-keepalive-max-default",
        "patterns": [r"\bmax\b", r"最大缓存", r"缓存实例数"],
        "stack": "vue",
    },
    {
        "key": "vue-suspense-timeout-default",
        "patterns": [r"timeout", r"后备内容", r"挂起"],
        "stack": "vue",
    },
    {
        "key": "vue-async-retry-count",
        "patterns": [r"重试|retry", r"加载失败", r"errorComponent"],
        "stack": "vue",
    },
    {
        "key": "vue-kebab-registered-pascal-usage",
        "patterns": [r"kebab-case", r"PascalCase"],
        "stack": "vue",
    },
    {
        "key": "vue-hydrate-on-idle-timeout",
        "patterns": [r"hydrateOnIdle", r"最大超时", r"requestIdleCallback"],
        "stack": "vue",
    },
]


def main() -> None:
    """逐条候选执行检索核验并打印命中。

    Returns:
        None。结果直接打印到标准输出。
    """
    corpus = loader.load()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for case in CASES:
        if only and only not in case["key"]:
            continue
        print("=" * 80)
        print("CASE:", case["key"], "stack:", case["stack"])
        for pat in case["patterns"]:
            hits = corpus.find(pat, stack=case["stack"], context=90, limit=8)
            print(f"-- pattern: {pat!r} -> {len(hits)} hit(s)")
            for h in hits:
                print(f"   [{h['doc']} | {h['section']} | {h['sec_start']}-{h['sec_end']}]")
                print("   ...", h["snippet"].replace("\n", " ")[:260])


if __name__ == "__main__":
    main()
