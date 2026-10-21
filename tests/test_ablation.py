"""消融实验的契约测试：对照组开关契约、跑通结构与指标范围。"""

from pathlib import Path

from ragkit.chunking import iter_heading_sections
from ragkit.config import AppConfig
from ragkit.evaluation import AnswerSection, Qrel, VARIANTS, run_ablation
from ragkit.index import build
from ragkit.text.normalize import normalize_text


def test_variants_contract():
    # 锁定 6 组单变量对照设计：对照组必须与默认值相反——
    # rerank_enabled 默认 True（加权排名融合），所以对照是"关掉它"（等权 RRF）；
    # 单腿组同时关 rerank，隔离变量；alpha_* 组只改融合权重，观察 α 敏感度。
    assert list(VARIANTS) == [
        "baseline",
        "alpha_09",
        "alpha_05",
        "no_rerank",
        "bm25_only",
        "dense_only",
    ]
    assert VARIANTS["baseline"] == {}
    assert VARIANTS["alpha_09"] == {"fusion_alpha": 0.9}
    assert VARIANTS["alpha_05"] == {"fusion_alpha": 0.5}
    assert VARIANTS["no_rerank"] == {"rerank_enabled": False}
    assert VARIANTS["bm25_only"] == {"dense_enabled": False, "rerank_enabled": False}
    assert VARIANTS["dense_only"] == {"sparse_enabled": False, "rerank_enabled": False}


def test_run_ablation_structure(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    text = "# 主题A\n\n## 小节1\n\n内容一\n\n## 小节2\n\n内容二\n"
    (raw / "a.md").write_text(text, encoding="utf-8")
    built = build(raw, AppConfig(index_dir=tmp_path / "idx"))

    # 小节级标注：只标"小节1"的字符区间，不依赖切出来的 chunk_id
    start, end = iter_heading_sections(normalize_text(text))[0]
    qrels = [Qrel(query="内容一", answers=(AnswerSection("a.md", "小节1", start, end),))]

    results = run_ablation(built, qrels)

    assert list(results) == [
        "baseline",
        "alpha_09",
        "alpha_05",
        "no_rerank",
        "bm25_only",
        "dense_only",
    ]
    for name, r in results.items():
        assert set(r["recall_at"]) == set(range(1, 11))
        assert 0.0 <= r["mrr"] <= 1.0
        assert all(0.0 <= v <= 1.0 for v in r["recall_at"].values())
