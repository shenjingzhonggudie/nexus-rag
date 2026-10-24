"""不依赖未分发正文的开发集完整性检查；精确原文另由check_qrels校验。"""

import hashlib
import json
from pathlib import Path

from ragkit.evaluation import load_qrels


DATA = Path(__file__).resolve().parents[1] / "data" / "eval"


def test_development_annotations_are_complete_and_manifest_matches():
    payload = (DATA / "qrels.json").read_bytes()
    rows = load_qrels(DATA / "qrels.json")
    manifest = json.loads((DATA / "annotation_manifest.json").read_text(encoding="utf-8"))
    reviews = [json.loads(line) for line in
               (DATA / "evidence_review.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r.id for r in rows} == {f"q_{i:04d}" for i in range(248)}
    assert len(rows) == len({r.query for r in rows}) == 248
    assert {r.annotation_version for r in rows} == {2}
    assert all(r.is_evaluable for r in rows)
    assert manifest["qrels_sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["counts"]["answer_points"] == sum(len(r.answer_points) for r in rows)
    assert manifest["counts"]["evidence_spans"] == sum(len(r.answers) for r in rows)
    assert manifest["counts"]["answerable"] == sum(not r.is_no_answer for r in rows)
    assert manifest["counts"]["no_answer"] == sum(r.is_no_answer for r in rows)
    assert len(reviews) == 248
    assert {r["sample_id"] for r in reviews} == {r.id for r in rows}
    for row in rows:
        if row.is_no_answer:
            assert row.unanswerable_reason.strip() and not row.answer_points
        else:
            assert row.answer_points
            assert all(p.point.strip() and p.evidence for p in row.answer_points)
            assert all(e.quote.strip() and len(e.quote) == e.end - e.start for e in row.answers)
            assert all(e.doc in manifest["corpus_sha256"] for e in row.answers)


def test_documented_v2_examples_load():
    rows = load_qrels(DATA / "qrels.example.json")
    assert {r.annotation_version for r in rows} == {2}
    assert any(r.is_no_answer for r in rows)
    assert any(r.answer_points for r in rows)
