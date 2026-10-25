"""消融实验的契约测试：对照组开关契约、跑通结构与指标范围。"""

from ragkit.chunking import iter_heading_sections
from ragkit.config import AppConfig, RerankConfig
from ragkit.evaluation import AnswerSection, Qrel, VARIANTS, run_ablation
from ragkit.index import build
from ragkit.text.normalize import normalize_text


def test_variants_contract():
    # 这六组只比较召回与融合。rrf名称不可暗示运行过真实模型重排。
    assert list(VARIANTS) == [
        "baseline",
        "alpha_09",
        "alpha_05",
        "rrf",
        "bm25_only",
        "dense_only",
    ]
    assert VARIANTS["baseline"] == {}
    assert VARIANTS["alpha_09"] == {"fusion_alpha": 0.9}
    assert VARIANTS["alpha_05"] == {"fusion_alpha": 0.5}
    assert VARIANTS["rrf"] == {"fusion_method": "rrf"}
    assert VARIANTS["bm25_only"] == {"dense_enabled": False, "fusion_method": "rrf"}
    assert VARIANTS["dense_only"] == {"sparse_enabled": False, "fusion_method": "rrf"}


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
        "rrf",
        "bm25_only",
        "dense_only",
    ]
    for name, r in results.items():
        assert set(r["recall_at"]) == set(range(1, 11))
        assert 0.0 <= r["mrr"] <= 1.0
        assert all(0.0 <= v <= 1.0 for v in r["recall_at"].values())
        assert r["rerank_config"] == RerankConfig(enabled=False).model_dump(mode="json")
        assert "rerank_enabled" not in r["config"]
        expected_method = (
            "weighted_rrf" if name in {"baseline", "alpha_09", "alpha_05"} else "rrf"
        )
        assert r["config"]["fusion_method"] == expected_method
        assert set(r["complete_at"]) == set(range(1, 11))
        assert r["scoring"]["mode"] == "section_overlap_legacy"
