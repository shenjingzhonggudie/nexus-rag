"""评测层：覆盖式指标、小节级标注加载、评测编排、消融实验。"""

from ragkit.evaluation.ablation import VARIANTS, run_ablation
from ragkit.evaluation.metrics import coverage_recall, first_hit_mrr
from ragkit.evaluation.qrels import QUERY_TYPES, AnswerPoint, AnswerSection, Qrel, load_qrels
from ragkit.evaluation.report import (
    EvalReport,
    LatencyStats,
    QueryResult,
    SourceStats,
    evaluate,
)

__all__ = [
    "AnswerSection",
    "AnswerPoint",
    "Qrel",
    "QUERY_TYPES",
    "load_qrels",
    "coverage_recall",
    "first_hit_mrr",
    "evaluate",
    "EvalReport",
    "LatencyStats",
    "QueryResult",
    "SourceStats",
    "run_ablation",
    "VARIANTS",
]
