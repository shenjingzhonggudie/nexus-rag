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
    monkeypatch.setattr(sys, "argv", [str(script), str(qrels), "--strict"])
    if valid_quote:
        checker.main()
        assert "全部通过" in capsys.readouterr().out
    else:
        with pytest.raises(SystemExit) as exc:
            checker.main()
        assert exc.value.code == 1
        assert "quote 与规范化原文区间不一致" in capsys.readouterr().out
