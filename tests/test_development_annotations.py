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
    assert len(rows) == 310
    assert len(rows) == len({r.query for r in rows})
    assert {r.annotation_version for r in rows} == {2}
    # 允许标注状态为 needs_review 的少量案例，它们不进指标分母；
    # 数量必须与 manifest 记录一致，不能悄悄增加。
    assert sum(not r.is_evaluable for r in rows) == manifest["counts"]["needs_review"]
    assert manifest["qrels_sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["counts"]["answer_points"] == sum(len(r.answer_points) for r in rows)
    assert manifest["counts"]["evidence_spans"] == sum(len(r.answers) for r in rows)
    assert manifest["counts"]["answerable"] == sum(not r.is_no_answer for r in rows)
    assert manifest["counts"]["no_answer"] == sum(r.is_no_answer for r in rows)
    # 复核日志记录逐条审阅过的案例；其余案例由各自的实验归档单独复核，
    # 因此这里只要求日志覆盖的 id 是评测集的子集，不要求一一对应。
    assert reviews
    assert {r["sample_id"] for r in reviews} <= {r.id for r in rows}
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
