"""评测编排：跑评测集、汇总指标、拒答表现与耗时（冷/热分开）。

判定口径（第 25 轮起）：
- **答案不绑切分**：qrels 标的是"文档 + 小节字符区间"，评测时只判断召回的
  块与答案区间**是否重叠**（同文档且区间相交）。换 chunk_size 或分块策略
  都不需要重标，也不会因为块边界挪动而误判。
- **无答案 query 不进 recall 平均**：它们没有标准答案，算 0 会把整体分数
  稀释成假低分；它们只参与拒答指标。
"""

import statistics
from dataclasses import dataclass, field

from ragkit.config import AppConfig
from ragkit.evaluation.metrics import coverage_recall, first_hit_mrr
from ragkit.evaluation.qrels import AnswerSection, Qrel
from ragkit.index.assets import BuiltIndex
from ragkit.retrieval.pipeline import search
from ragkit.schemas import Chunk


def _extract_chunk_ids(results) -> list[str]:
    """从检索结果提取 chunk_id 序列，仅供明细与诊断。"""
    return [sc.chunk.chunk_id for sc in results]


def _hit_indices(chunk: Chunk, answers: tuple[AnswerSection, ...]) -> set[int]:
    """块命中了哪些答案小节：同文档、且字符区间相交。

    用"区间相交"而不是"区间包含"：块边界随切分策略变化，只要块与答案小节
    有任何重叠就算命中，避免因为切分把答案切开而误判为未命中。

    Args:
        chunk: 检索召回的块。
        answers: 该 query 的答案小节。

    Returns:
        set[int]: 命中的答案小节下标集合；无命中为空集。
    """
    char_start = chunk.metadata.get("char_start")
    char_end = chunk.metadata.get("char_end")
    if char_start is None or char_end is None:
        return set()

    hits: set[int] = set()
    for index, answer in enumerate(answers):
        if chunk.doc_id != answer.doc:
            continue
        if char_start < answer.end and char_end > answer.start:
            hits.add(index)
    return hits


@dataclass
class QueryResult:
    """单条 query 的评测明细，供消融逐条对比。"""

    query: str
    query_type: str               # direct / paraphrase / multi_block / cross_doc / no_answer
    retrieved: list[str]          # 检索返回的 chunk_id 序列
    hits_per_rank: list[list[int]]  # 每个结果命中的答案小节下标（便于核对）
    recall_at: dict[int, float]   # k -> 覆盖率
    mrr: float
    total_ms: float               # 检索 trace 总耗时
    refused: bool = False         # 是否被判定为拒答
    is_no_answer: bool = False    # 是否为无答案 query
    match_score: float | None = None  # 查询实词被检索结果覆盖的比例
    source: str = "internal"      # internal（读正文出题）/ external（只看标题出题）


@dataclass
class SourceStats:
    """按题目来源分组的检索指标（用于对比"出题视角"的差距）。"""

    n: int                        # 有答案 query 数
    recall_at: dict[int, float]   # k -> 覆盖率
    mrr: float


@dataclass
class LatencyStats:
    """耗时表：冷启动（首查）与热启动（后续查询）分开。"""

    cold_ms: float
    warm_mean_ms: float
    warm_p50_ms: float
    warm_p95_ms: float


@dataclass
class EvalReport:
    """一次评测的汇总报告。"""

    recall_at: dict[int, float]   # 各 k 的平均覆盖率（只统计有答案 query）
    mrr: float                    # 平均 mrr（只统计有答案 query）
    per_query: list[QueryResult]  # 明细
    latency: LatencyStats
    refusal_accuracy: float = 0.0    # 无答案 query 上的正确拒答率
    false_refusal_rate: float = 0.0  # 有答案 query 上的误拒率
    n_no_answer: int = 0             # 无答案 query 数
    by_source: dict[str, SourceStats] = field(default_factory=dict)  # 按来源分组
    # 本次评测实际生效的配置（AppConfig.snapshot()，api_key 已脱敏）。
    # 不记录的话，报告只能说明"这组数字是多少"，无法回答"它是用哪个配置跑出来的"。
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为 JSON 兼容的字典（落盘 / API 输出用）。"""
        return {
            "config": self.config,
            "recall_at": self.recall_at,
            "mrr": self.mrr,
            "refusal": {
                "accuracy": self.refusal_accuracy,
                "false_rate": self.false_refusal_rate,
                "n_no_answer": self.n_no_answer,
            },
            "by_source": {
                name: {"n": stats.n, "recall_at": stats.recall_at, "mrr": stats.mrr}
                for name, stats in self.by_source.items()
            },
            "per_query": [
                {
                    "query": q.query,
                    "type": q.query_type,
                    "retrieved": q.retrieved,
                    "hits_per_rank": q.hits_per_rank,
                    "recall_at": q.recall_at,
                    "mrr": q.mrr,
                    "total_ms": q.total_ms,
                    "refused": q.refused,
                    "is_no_answer": q.is_no_answer,
                    "match_score": q.match_score,
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


def _effective_snapshot(cfg: AppConfig) -> dict:
    """配置快照，但把 embedding 段换成**实际生效**的 provider。

    ``cfg.embedding.provider`` 是配置声明值；``load_index`` 会按索引 manifest
    的 provider 再调一次 ``configure()``。配置默认 ``hashing`` 而索引是 ``bge``
    时，若只记声明值，报告会写着 hashing 却实际跑 bge —— 可追溯性变成误导。

    Args:
        cfg: 本次评测使用的应用配置。

    Returns:
        dict: JSON 兼容快照；``embedding.provider`` 为实际值，
            ``embedding.provider_configured`` 保留配置声明值以便对照。
    """
    from ragkit.embeddings import active

    snapshot = cfg.snapshot()
    provider, model_name = active()
    embedding = snapshot.setdefault("embedding", {})
    embedding["provider_configured"] = embedding.get("provider")
    embedding["provider"] = provider
    if model_name:
        embedding["model_name"] = model_name
    return snapshot


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


def _is_refused(
    results: list, match_score: float | None, threshold: float
) -> bool:
    """按与生成层一致的规则判定是否拒答。

    两处必须同步修改：这里是评测视角的复算，``generation/answer.py`` 是线上
    视角的判定；规则不一致会让评测报出的拒答率与实际行为脱节。
    """
    if not results:
        return True
    return threshold > 0.0 and match_score is not None and match_score < threshold


def evaluate(
    built: BuiltIndex,
    cfg: AppConfig,
    qrels: list[Qrel],
    *,
    ks: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
) -> EvalReport:
    """对全部评测样例跑检索并汇总指标、拒答表现与耗时。

    Args:
        built: 已建好的索引。
        cfg: 应用配置（retrieval 开关、top_k/final_k 与拒答阈值）。
        qrels: 评测样例；``answers`` 为空表示无答案 query。
        ks: 要统计的 recall 截断位置。

    Returns:
        EvalReport: 有答案 query 的平均 recall@k / mrr、无答案 query 的拒答
            准确率、有答案 query 的误拒率、逐条明细、冷/热耗时表。
            qrels 为空时返回全 0 报告（不除零）。
    """
    per_query: list[QueryResult] = []
    warm_ms: list[float] = []
    cold_ms = 0.0
    threshold = cfg.retrieval.refuse_threshold

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
            # 进程内首次 search：不含 jieba（build/load_index 时已加载），
            # 但含首次查询的一次性开销。完整冷启动发生在 build/load_index 层。
            cold_ms = total
        else:
            warm_ms.append(total)

        hits_per_rank = [
            sorted(_hit_indices(sc.chunk, qrel.answers)) for sc in result.results
        ]
        total_answers = len(qrel.answers)

        per_query.append(
            QueryResult(
                query=qrel.query,
                query_type=qrel.type,
                retrieved=_extract_chunk_ids(result.results),
                hits_per_rank=hits_per_rank,
                recall_at={
                    k: coverage_recall(hits_per_rank, total_answers, k) for k in ks
                },
                mrr=first_hit_mrr(hits_per_rank),
                total_ms=total,
                refused=_is_refused(result.results, result.match_score, threshold),
                is_no_answer=qrel.is_no_answer,
                match_score=result.match_score,
                source=qrel.source,
            )
        )

    if not per_query:
        return EvalReport(
            recall_at={k: 0.0 for k in ks},
            mrr=0.0,
            per_query=[],
            latency=LatencyStats(0.0, 0.0, 0.0, 0.0),
            config=_effective_snapshot(cfg),
        )

    no_answer = [q for q in per_query if q.is_no_answer]
    answerable = [q for q in per_query if not q.is_no_answer]

    # 检索质量只在有答案 query 上平均：无答案 query 没有标准答案，算 0 会稀释
    n_answerable = len(answerable)
    recall_at = {
        k: (
            sum(q.recall_at[k] for q in answerable) / n_answerable
            if n_answerable
            else 0.0
        )
        for k in ks
    }
    mrr_avg = sum(q.mrr for q in answerable) / n_answerable if n_answerable else 0.0

    refusal_accuracy = (
        sum(1 for q in no_answer if q.refused) / len(no_answer) if no_answer else 0.0
    )
    false_refusal_rate = (
        sum(1 for q in answerable if q.refused) / n_answerable if n_answerable else 0.0
    )

    # 按来源分组：分母同样只算有答案 query，否则 external 组会被 no_answer 稀释
    by_source: dict[str, SourceStats] = {}
    # internal 排在最前（它是主基准），其余按字母序
    for source in sorted({q.source for q in per_query}, key=lambda s: (s != "internal", s)):
        rows = [q for q in per_query if q.source == source and not q.is_no_answer]
        if not rows:
            continue
        n_source = len(rows)
        by_source[source] = SourceStats(
            n=n_source,
            recall_at={k: sum(r.recall_at[k] for r in rows) / n_source for k in ks},
            mrr=sum(r.mrr for r in rows) / n_source,
        )

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
        refusal_accuracy=refusal_accuracy,
        false_refusal_rate=false_refusal_rate,
        n_no_answer=len(no_answer),
        by_source=by_source,
        config=_effective_snapshot(cfg),
    )
