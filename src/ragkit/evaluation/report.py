"""评测编排：跑评测集、汇总指标、生成耗时表（冷/热分开）。"""

import statistics
from dataclasses import dataclass

from ragkit.config import AppConfig
from ragkit.evaluation.metrics import mrr, recall_at_k
from ragkit.evaluation.qrels import Qrel
from ragkit.index.assets import BuiltIndex
from ragkit.retrieval.pipeline import search


def _extract_chunk_ids(results) -> list[str]:
    """从检索结果提取 chunk_id 序列（块级评测单元）。

    评测单元是块（chunk，对应文档里的一个 ``##`` 小节）：标注和检索都按
    chunk_id 对齐。融合已按 chunk_id 去重，直接提取即可。
    """
    return [sc.chunk.chunk_id for sc in results]


@dataclass
class QueryResult:
    """单条 query 的评测明细，供消融逐条对比。"""

    query: str
    retrieved: list[str]          # 检索返回的 chunk_id 序列
    recall_at: dict[int, float]   # k -> recall
    mrr: float
    total_ms: float               # 检索 trace 总耗时


@dataclass
class LatencyStats:
    """耗时表：冷启动（首查含 jieba 加载）与热启动（后续查询）分开。"""

    cold_ms: float
    warm_mean_ms: float
    warm_p50_ms: float
    warm_p95_ms: float


@dataclass
class EvalReport:
    """一次评测的汇总报告。"""

    recall_at: dict[int, float]   # 各 k 的平均 recall
    mrr: float                    # 平均 mrr
    per_query: list[QueryResult]  # 明细
    latency: LatencyStats

    def to_dict(self) -> dict:
        """序列化为 JSON 兼容的字典（落盘 / API 输出用）。"""
        return {
            "recall_at": self.recall_at,
            "mrr": self.mrr,
            "per_query": [
                {
                    "query": q.query,
                    "retrieved": q.retrieved,
                    "recall_at": q.recall_at,
                    "mrr": q.mrr,
                    "total_ms": q.total_ms,
                }
                for q in self.per_query
            ],
            "latency": {
                "cold_ms": self.latency.cold_ms,
                "warm_mean_ms": self.latency.warm_mean_ms,
                "warm_p50_ms": self.latency.warm_p50_ms,
                "warm_p95_ms": self.latency.warm_p95_ms,
            },
        }


def _percentile(data: list[float], p: float) -> float:
    """线性插值分位数（与 numpy 默认一致）；空数据返回 0.0。"""
    if not data:
        return 0.0
    ordered = sorted(data)
    idx = (len(ordered) - 1) * p
    lower = int(idx)
    upper = min(lower + 1, len(ordered) - 1)
    weight = idx - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def evaluate(
    built: BuiltIndex,
    cfg: AppConfig,
    qrels: list[Qrel],
    *,
    ks: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
) -> EvalReport:
    """对全部评测样例跑检索并汇总指标与耗时。

    Args:
        built: 已建好的索引。
        cfg: 应用配置（retrieval 开关与 top_k/final_k）。
        qrels: 评测样例。
        ks: 要统计的 recall 截断位置。

    Returns:
        EvalReport: 平均 recall@k、平均 mrr、逐条明细、冷/热耗时表。
            qrels 为空时返回全 0 报告（不除零）。
    """
    per_query: list[QueryResult] = []
    warm_ms: list[float] = []
    cold_ms = 0.0

    for i, qrel in enumerate(qrels):
        result = search(
            qrel.query,
            bm25=built.bm25,
            store=built.store,
            id_to_chunk=built.id_to_chunk,
            dim=built.dim,
            retrieval=cfg.retrieval,
        )
        total = result.trace.total_latency_ms()
        if i == 0:
            # 进程内首次 search：不含 jieba（build/load_index 时已加载，见债务 9），
            # 但含首次查询的一次性开销。完整冷启动（jieba 约 1.8s + BM25 重建分词）
            # 发生在 build/load_index 层，不属检索耗时——评测只关心检索各阶段的热耗时。
            cold_ms = total
        else:
            warm_ms.append(total)

        chunks = _extract_chunk_ids(result.results)
        per_query.append(
            QueryResult(
                query=qrel.query,
                retrieved=chunks,
                recall_at={k: recall_at_k(chunks, qrel.relevant, k) for k in ks},
                mrr=mrr(chunks, qrel.relevant),
                total_ms=total,
            )
        )

    if not per_query:
        return EvalReport(
            recall_at={k: 0.0 for k in ks},
            mrr=0.0,
            per_query=[],
            latency=LatencyStats(0.0, 0.0, 0.0, 0.0),
        )

    n = len(per_query)
    recall_at = {k: sum(q.recall_at[k] for q in per_query) / n for k in ks}
    mrr_avg = sum(q.mrr for q in per_query) / n
    return EvalReport(
        recall_at=recall_at,
        mrr=mrr_avg,
        per_query=per_query,
        latency=LatencyStats(
            cold_ms=cold_ms,
            warm_mean_ms=statistics.mean(warm_ms) if warm_ms else 0.0,
            warm_p50_ms=_percentile(warm_ms, 0.5),
            warm_p95_ms=_percentile(warm_ms, 0.95),
        ),
    )
