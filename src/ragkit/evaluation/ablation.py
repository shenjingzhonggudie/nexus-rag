"""消融实验：逐个关闭组件，量化每个组件的边际贡献。

第 19 轮决策 1：单变量控制——每次只动一个开关，其余保持 baseline。
关键约束：单腿组（只 BM25 / 只 dense）必须同时关 rerank，否则 rerank 会
拿 dense 向量给 BM25 召回精排，混入另一条腿的信息，就不是"纯单腿"了。
"""

from ragkit.config import AppConfig, RetrievalConfig
from ragkit.evaluation.qrels import Qrel
from ragkit.evaluation.report import evaluate
from ragkit.index.assets import BuiltIndex

# 6 组对照：组名 -> RetrievalConfig 的覆盖项（其余用默认值）
#
# 对照组必须与默认值**相反**才有信息量：
# - `rerank_enabled` 默认 True（加权排名融合 S = α·S1 + (1−α)·S2），
#   所以"关掉它"（退化为等权 RRF）才是有意义的对照；
# - 单腿组同时关 rerank：否则 rerank 会把另一条腿也拉进来算加权，就不是纯单腿了；
# - `fusion_alpha` 默认 0.7（221 条上最优）。所以 α 扫描点是 **0.5 / 0.7(默认) / 0.9**：
#   `alpha_05` 应与 `no_rerank` 几乎一致（α=0.5 等价于等权 RRF），可当自洽性检查。
VARIANTS: dict[str, dict] = {
    "baseline": {},                                          # 加权排名融合（默认，α=0.7）
    "alpha_09": {"fusion_alpha": 0.9},                       # 更偏 BM25（旧默认，看差多少）
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
        dict[str, dict]: 组名（baseline / with_rerank / bm25_only / dense_only）
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
