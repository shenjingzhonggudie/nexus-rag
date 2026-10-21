"""消融实验的契约测试：对照组开关契约、跑通结构与指标范围。"""

from pathlib import Path

from ragkit.config import AppConfig
from ragkit.evaluation import Qrel, VARIANTS, run_ablation
from ragkit.index import build


def test_variants_contract():
    # 锁定 4 组单变量对照设计：单腿组必须同时关 rerank（隔离变量）
    assert list(VARIANTS) == ["baseline", "bm25_only", "dense_only", "no_rerank"]
    assert VARIANTS["baseline"] == {}
    assert VARIANTS["bm25_only"] == {"dense_enabled": False, "rerank_enabled": False}
    assert VARIANTS["dense_only"] == {"sparse_enabled": False, "rerank_enabled": False}
    assert VARIANTS["no_rerank"] == {"rerank_enabled": False}


def test_run_ablation_structure(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text(
        "# 主题A\n\n## 小节1\n\n内容一\n\n## 小节2\n\n内容二\n", encoding="utf-8"
    )
    built = build(raw, AppConfig(index_dir=tmp_path / "idx"))
    qrels = [Qrel(query="内容一", relevant=frozenset([built.store.ids[0]]))]

    results = run_ablation(built, qrels)

    assert list(results) == ["baseline", "bm25_only", "dense_only", "no_rerank"]
    for name, r in results.items():
        assert set(r["recall_at"]) == set(range(1, 11))
        assert 0.0 <= r["mrr"] <= 1.0
        assert all(0.0 <= v <= 1.0 for v in r["recall_at"].values())
