"""评测层：检索质量指标（recall@k / MRR）、评测集加载、评测编排、消融实验。"""

from ragkit.evaluation.ablation import VARIANTS, run_ablation
from ragkit.evaluation.metrics import mrr, recall_at_k
from ragkit.evaluation.qrels import Qrel, load_qrels
from ragkit.evaluation.report import EvalReport, LatencyStats, QueryResult, evaluate

__all__ = [
    "Qrel",
    "load_qrels",
    "recall_at_k",
    "mrr",
    "evaluate",
    "EvalReport",
    "LatencyStats",
    "QueryResult",
    "run_ablation",
    "VARIANTS",
]
