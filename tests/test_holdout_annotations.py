"""冻结标注的完整性检查；不读取历史评分或逐题输出。"""

import hashlib
import json
from pathlib import Path

from ragkit.evaluation import load_qrels


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "experiments" / "holdout-evidence-v2"


def test_frozen_holdout_labels_preserve_questions_and_hashes():
    frozen = json.loads((DATA / "ANNOTATION_FREEZE.json").read_text(encoding="utf-8"))
    qrels = load_qrels(DATA / "qrels.v2.json")
    original = json.loads((ROOT / "experiments/holdout-v1/sealed/qrels.test.json").read_text(encoding="utf-8"))
    assert len(qrels) == len(original) == 62
    assert [(q.id, q.query, q.source) for q in qrels] == [
        (q["id"], q["query"], q["source"]) for q in original]
    assert {q.annotation_version for q in qrels} == {2}
    for name, key in (("qrels.v2.json", "qrels_sha256"),
                      ("annotation_review.jsonl", "review_sha256"),
                      ("PROTOCOL.md", "protocol_sha256")):
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == frozen[key]
    assert frozen["phase"] == "answers_frozen_before_opening_saved_outputs"
    assert frozen["output_access"]["during_reannotation"] is False
    assert frozen["scoring"]["comparison"] == ">"
    assert frozen["scoring"]["threshold"] == 0.5
    reviews = [json.loads(s) for s in (DATA / "annotation_review.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(reviews) == len({q["id"] for q in reviews}) == 62
    assert {q["id"] for q in reviews} == {q.id for q in qrels}
    assert frozen["counts"]["pending"] == sum(not q.is_evaluable for q in qrels)
    assert frozen["counts"]["answerable"] == sum(not q.is_no_answer for q in qrels)
    assert frozen["counts"]["no_answer"] == sum(q.is_no_answer for q in qrels)
    assert frozen["counts"]["points"] == sum(len(q.answer_points) for q in qrels)
    assert frozen["counts"]["evidence_spans"] == sum(len(q.answers) for q in qrels)
