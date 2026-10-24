"""六组检索配置对照，共用索引及同版本标注，并保留实际配置与判分口径。"""

from ragkit.config import AppConfig, RetrievalConfig
from ragkit.evaluation.qrels import Qrel
from ragkit.evaluation.report import evaluate
from ragkit.index.assets import BuiltIndex

# 6 组对照：组名 -> RetrievalConfig 的覆盖项（其余用默认值）
#
# rerank开关控制加权排名融合或等权RRF，只融合已启用的通道。
# 单路组沿用等权RRF设置；不会额外调用被关闭的检索通道。
# alpha扫描为0.5/0.7/0.9；这些取值不代表已证明的最优参数。
VARIANTS: dict[str, dict] = {
    "baseline": {},                                          # 加权排名融合（默认，α=0.7）
    "alpha_09": {"fusion_alpha": 0.9},                       # 更偏 BM25
    "alpha_05": {"fusion_alpha": 0.5},                       # 等权（应≈no_rerank）
    "no_rerank": {"rerank_enabled": False},                  # 完全关掉加权，退化为等权 RRF
    "bm25_only": {"dense_enabled": False, "rerank_enabled": False},
    "dense_only": {"sparse_enabled": False, "rerank_enabled": False},
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
        dict[str, dict]: VARIANTS组名到recall_at、mrr、complete_at、config及scoring的映射。
            键顺序即 VARIANTS 顺序；``config`` 是该组实际生效的检索配置，
            没有它就无法从落盘结果回溯"这一行是哪个开关组合跑出来的"。
    """
    results: dict[str, dict] = {}
    for name, overrides in VARIANTS.items():
        # 构造该组的检索配置（默认值 + 覆盖项），其余配置字段 evaluate 不读
        report = evaluate(
            built, AppConfig(retrieval=RetrievalConfig(**overrides)), qrels, ks=ks
        )
        results[name] = {
            "recall_at": report.recall_at,
            "mrr": report.mrr,
            "config": report.config.get("retrieval", {}),
            "scoring": report.scoring,
            "complete_at": report.complete_at,
        }
    return results
