"""盲测集接口：当前为空；一旦有数据，必须与回归集完全隔离。"""

import json
from pathlib import Path

from ragkit.evaluation import load_qrels

ROOT = Path(__file__).resolve().parents[1]
BLIND = ROOT / "data" / "eval" / "blind" / "qrels.blind.json"
REG = ROOT / "data" / "eval" / "qrels.regression.json"


def test_blind_file_exists_and_parses():
    """接口必须可用：空数组也能被 load_qrels 正常加载。"""
    assert BLIND.exists()
    assert isinstance(load_qrels(BLIND), list)


def test_blind_cases_follow_naming_and_origin():
    """当前无数据；将来加入的每条都必须 origin=blind 且 id 以 b_ 开头。"""
    blind = load_qrels(BLIND)
    for item in blind:
        assert item.origin == "blind", f"{item.id} 的 origin 不是 blind"
        assert item.id.startswith("b_"), f"{item.id} 未使用 b_ 前缀"
        assert item.annotation_version == 2


def test_blind_does_not_overlap_regression():
    """盲测集不能复用回归集的任何一条（id 和 query 文本都不能重复）。"""
    blind_raw = json.loads(BLIND.read_text(encoding="utf-8"))
    reg_raw = json.loads(REG.read_text(encoding="utf-8"))

    blind_ids = {q.get("id") for q in blind_raw}
    reg_ids = {q.get("id") for q in reg_raw}
    assert not (blind_ids & reg_ids), f"id 重叠: {blind_ids & reg_ids}"

    blind_q = {str(q.get("query", "")).strip() for q in blind_raw}
    reg_q = {str(q.get("query", "")).strip() for q in reg_raw}
    assert not (blind_q & reg_q), f"query 重叠: {len(blind_q & reg_q)} 条"
