"""标注检查必须使用加载后的原文，并允许v2导语证据。"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ragkit.loaders import load_file
from ragkit.text import normalize_text


@pytest.mark.parametrize("valid_quote", [True, False])
def test_v2_checker_accepts_intro_and_rejects_wrong_quote(tmp_path, monkeypatch, capsys, valid_quote):
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_qrels.py"
    spec = importlib.util.spec_from_file_location("check_qrels_under_test", script)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    raw = tmp_path / "raw"
    raw.mkdir()
    doc = raw / "a.md"
    doc.write_text("---\ntitle: 示例\n---\n\n查询只取需要的列。\n\n## 其他\n\n其他内容。", encoding="utf-8")
    quote = "查询只取需要的列。"
    normalized = normalize_text(load_file(doc).text)
    start = normalized.index(quote)
    qrels = tmp_path / "qrels.json"
    qrels.write_text(json.dumps([{
        "id": "q_intro", "query": "取哪些列？", "type": "direct", "annotation_version": 2,
        "answers": [{"point": quote, "evidence": [{"doc": "a.md", "section": "导语",
                     "start": start, "end": start + len(quote),
                     "quote": quote if valid_quote else "错" * len(quote)}]}],
    }], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(checker, "RAW_DIR", raw)
    # 本测试只检查证据坐标；单题样例不承担真实题型配比要求。
    monkeypatch.setattr(checker, "TARGET_RATIO", {
        qtype: float(qtype == "direct") for qtype in checker.QUERY_TYPES
    })
    monkeypatch.setattr(sys, "argv", [str(script), str(qrels), "--strict"])
    if valid_quote:
        checker.main()
        assert "全部通过" in capsys.readouterr().out
    else:
        with pytest.raises(SystemExit) as exc:
            checker.main()
        assert exc.value.code == 1
        assert "quote 与规范化原文区间不一致" in capsys.readouterr().out


def _ratio_fixture(tmp_path, monkeypatch, delta, strict):
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_qrels.py"
    spec = importlib.util.spec_from_file_location("check_qrels_ratio_under_test", script)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    raw = tmp_path / "raw"
    raw.mkdir()
    quote = "查询只取需要的列。"
    (raw / "a.md").write_text(quote, encoding="utf-8")
    counts = {"direct": 30, "paraphrase": 30 + delta, "multi_block": 15 - delta,
              "cross_doc": 10, "no_answer": 15}
    rows = []
    for qtype, count in counts.items():
        for index in range(count):
            item = {"id": f"{qtype}_{index}", "query": f"{qtype}问题{index}",
                    "type": qtype, "annotation_version": 2}
            if qtype == "no_answer":
                item.update(answers=[], unanswerable_reason="原文没有此项信息")
            else:
                item["answers"] = [{"point": quote, "evidence": [{
                    "doc": "a.md", "start": 0, "end": len(quote), "quote": quote,
                }]}]
            rows.append(item)
    qrels = tmp_path / "qrels.json"
    qrels.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(checker, "RAW_DIR", raw)
    monkeypatch.setattr(sys, "argv", [str(script), str(qrels)] + (["--strict"] if strict else []))
    return checker


@pytest.mark.parametrize("delta", [-8, 8])
def test_strict_accepts_exact_eight_percentage_point_deviation(tmp_path, monkeypatch, capsys, delta):
    checker = _ratio_fixture(tmp_path, monkeypatch, delta=delta, strict=True)

    checker.main()

    out = capsys.readouterr().out
    assert "全部通过" in out
    assert "偏离超过8个百分点" not in out


@pytest.mark.parametrize("strict", [False, True])
def test_ratio_deviation_warns_and_only_fails_in_strict_mode(tmp_path, monkeypatch, capsys, strict):
    checker = _ratio_fixture(tmp_path, monkeypatch, delta=9, strict=strict)

    if strict:
        with pytest.raises(SystemExit) as exc:
            checker.main()
        assert exc.value.code == 1
    else:
        checker.main()

    out = capsys.readouterr().out
    assert "2 个警告" in out
    assert "题型配比 multi_block: 实际 6.0%，建议 15%" in out
    assert "偏离超过8个百分点" in out
    assert "全部通过" not in out
