"""消融实验：逐个关闭组件，量化每个组件的边际贡献。

第 19 轮决策 1：单变量控制——每次只动一个开关，其余保持 baseline。
关键约束：单腿组（只 BM25 / 只 dense）必须同时关 rerank，否则 rerank 会
拿 dense 向量给 BM25 召回精排，混入另一条腿的信息，就不是"纯单腿"了。
"""

from ragkit.config import AppConfig, RetrievalConfig
from ragkit.evaluation.qrels import Qrel
from ragkit.evaluation.report import evaluate
from ragkit.index.assets import BuiltIndex

# 4 组对照：组名 -> RetrievalConfig 的覆盖项（其余用默认值）
VARIANTS: dict[str, dict] = {
    "baseline": {},
    "bm25_only": {"dense_enabled": False, "rerank_enabled": False},
    "dense_only": {"sparse_enabled": False, "rerank_enabled": False},
    "no_rerank": {"rerank_enabled": False},
}


def run_ablation(
    built: BuiltIndex,
    qrels: list[Qrel],
    *,
    ks: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
) -> dict[str, dict]:
    """对每个对照组跑完整评测，返回 组名 -> 指标摘要。

    Args:
        built: 已建好的索引（各对照组共用同一个索引，只变检索开关）。
        qrels: 评测样例。
        ks: recall 截断位置。

    Returns:
        dict[str, dict]: 组名（baseline / bm25_only / dense_only / no_rerank）
            -> {"recall_at": {k: float}, "mrr": float}。键顺序即 VARIANTS 顺序。
    """
    results: dict[str, dict] = {}
    for name, overrides in VARIANTS.items():
        # 构造该组的检索配置（默认值 + 覆盖项），其余配置字段 evaluate 不读
        report = evaluate(
            built, AppConfig(retrieval=RetrievalConfig(**overrides)), qrels, ks=ks
        )
        results[name] = {"recall_at": report.recall_at, "mrr": report.mrr}
    return results
