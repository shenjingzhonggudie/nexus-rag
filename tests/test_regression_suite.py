"""310 题回归集：规模、来源、口径，以及"合并只加 origin"的契约。"""

import importlib.util
import json
from collections import Counter
from pathlib import Path

from ragkit.evaluation import load_qrels

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "data" / "eval" / "qrels.regression.json"
DEV = ROOT / "data" / "eval" / "qrels.json"
HOLD = ROOT / "experiments" / "holdout-evidence-v2" / "qrels.v2.json"


def _build_module():
    """加载构建脚本（scripts/ 不是包，用 importlib 按路径加载）。"""
    spec = importlib.util.spec_from_file_location(
        "build_regression_suite", ROOT / "scripts" / "build_regression_suite.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_regression_suite_has_310_cases():
    assert len(load_qrels(REG)) == 310


def test_origins_are_the_two_known_batches():
    counts = Counter(q.origin for q in load_qrels(REG))
    assert counts == {"original_248": 248, "original_62": 62}


def test_all_cases_use_v2_scoring():
    assert {q.annotation_version for q in load_qrels(REG)} == {2}


def test_ids_are_unique_and_non_empty():
    ids = [q.id for q in load_qrels(REG)]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_no_duplicate_queries():
    texts = Counter(q.query.strip() for q in load_qrels(REG))
    assert [t for t, n in texts.items() if n > 1] == []


def test_merge_only_adds_origin():
    """合并时除 origin 外的字段必须与源文件逐条一致，不能顺手改标准答案。"""
    merged = {
        item["id"]: item
        for item in json.loads(REG.read_text(encoding="utf-8"))
    }
    for source_file in (DEV, HOLD):
        for item in json.loads(source_file.read_text(encoding="utf-8")):
            got = merged[item["id"]]
            for key in ("query", "type", "source", "annotation_version", "annotation_status"):
                assert got[key] == item[key], f"{item['id']} 的 {key} 被改动"
            assert got["answers"] == item["answers"], f"{item['id']} 的 answers 被改动"


def test_build_is_reproducible():
    """重新构建必须与磁盘文件完全一致，否则说明文件被手工改过。"""
    rebuilt = _build_module().build()
    on_disk = json.loads(REG.read_text(encoding="utf-8"))
    assert rebuilt == on_disk
