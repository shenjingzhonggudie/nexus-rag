"""六组召回与融合配置对照；显式关闭真实模型重排，并记录各组实际配置。"""

from ragkit.config import AppConfig, RerankConfig, RetrievalConfig
from ragkit.evaluation.qrels import Qrel
from ragkit.evaluation.report import evaluate
from ragkit.index.assets import BuiltIndex

# 6 组对照：组名 -> RetrievalConfig 的覆盖项（其余用默认值）
#
# fusion_method选择加权或等权RRF，只融合已启用的通道。
# 单路组沿用等权RRF设置；所有组均显式关闭真实模型重排。
# alpha扫描为0.5/0.7/0.9；这些取值不代表已证明的最优参数。
VARIANTS: dict[str, dict] = {
    "baseline": {},                                          # 加权排名融合（默认，α=0.7）
    "alpha_09": {"fusion_alpha": 0.9},                       # 更偏 BM25
    "alpha_05": {"fusion_alpha": 0.5},                       # 与等权RRF排序一致
    "rrf": {"fusion_method": "rrf"},                        # 等权RRF，不是关闭模型的对照
    "bm25_only": {"dense_enabled": False, "fusion_method": "rrf"},
    "dense_only": {"sparse_enabled": False, "fusion_method": "rrf"},
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
        dict[str, dict]: VARIANTS组名到指标、config、rerank_config及scoring的映射。
            键顺序即 VARIANTS 顺序；``config`` 是该组实际生效的检索配置，
            ``rerank_config`` 单独记录真实模型重排配置。这六组不评估其效果。
            Recall/MRR为全部定稿可答题的按题宏平均，不按source分组；
            无答案与待复核题不进入该分母。
    """
    results: dict[str, dict] = {}
    for name, overrides in VARIANTS.items():
        # 六组只比较召回与融合，显式关闭模型，不受应用默认值变化影响。
        report = evaluate(
            built,
            AppConfig(
                retrieval=RetrievalConfig(**overrides),
                rerank=RerankConfig(enabled=False),
            ),
            qrels,
            ks=ks,
        )
        results[name] = {
            "recall_at": report.recall_at,
            "mrr": report.mrr,
            "config": report.config.get("retrieval", {}),
            "rerank_config": report.config.get("rerank", {}),
            "scoring": report.scoring,
            "complete_at": report.complete_at,
        }
    return results
