"""Independently verify saved-output regrading using character-position sets.

Uses only the standard library and committed offsets; never imports the production
coverage/replay implementation. Does not certify the semantics of annotations.
"""

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "experiments/holdout-evidence-v2"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a, b):
    if not math.isclose(a, b, rel_tol=0, abs_tol=1e-12):
        raise ValueError(f"Independent arithmetic disagreement: {a} != {b}")


def main():
    freeze = load(DATA / "ANNOTATION_FREEZE.json")
    manifest = load(DATA / "RESCORE_MANIFEST.json")
    if digest(DATA / "qrels.v2.json") != freeze["qrels_sha256"]:
        raise ValueError("Frozen label hash mismatch")
    if digest(DATA / "retrieved_intervals.json") != manifest["retrieved_intervals_sha256"]:
        raise ValueError("Retrieved interval snapshot hash mismatch")
    questions = load(DATA / "qrels.v2.json")
    intervals = load(DATA / "retrieved_intervals.json")
    audit = []
    verification = {"method":"independent_character_position_sets",
                    "production_coverage_imported":False, "qrels_sha256":freeze["qrels_sha256"],
                    "retrieved_intervals_sha256":manifest["retrieved_intervals_sha256"],
                    "checker_canonical_lf_sha256":hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n",b"\n")).hexdigest(),
                    "configs":{}}
    for label in "AB":
        meta = manifest["configs"][label]
        saved_path = ROOT / meta["saved_report"]
        if digest(saved_path) != meta["saved_report_sha256"] or digest(DATA / meta["result"]) != meta["result_sha256"]:
            raise ValueError("Saved output or regrade hash mismatch")
        saved_rows = load(saved_path)["per_query"]
        saved = {r["query"]:r for r in saved_rows}
        report = load(DATA / meta["result"])
        actual_rows = report["per_query"]
        actual = {r["id"]:r for r in actual_rows}
        if len(saved) != len(saved_rows) or set(saved) != {q["query"] for q in questions}:
            raise ValueError("Queries are not a one-to-one match")
        if len(actual) != len(actual_rows) or set(actual) != {q["id"] for q in questions}:
            raise ValueError("Regrade rows are not a one-to-one match")
        independent = []
        for q in questions:
            row = saved[q["query"]]
            a = actual[q["id"]]
            if row["retrieved"] != a["retrieved"] or row["refused"] != a["refused"]:
                raise ValueError("Saved ranks or refusal flag changed")
            evaluated = q["annotation_status"] != "needs_review"
            if (a["query"] != q["query"] or a["annotation_status"] != q["annotation_status"]
                    or a["evaluated"] != evaluated or a["is_no_answer"] != (q["type"] == "no_answer")
                    or a["point_labels"] != [p["point"] for p in q["answers"]]):
                raise ValueError("Regrade metadata differs from frozen question")
            if len(a["hits_by_prefix"]) != len(row["retrieved"]) or len(a["point_coverage_by_prefix"]) != len(row["retrieved"]):
                raise ValueError("Wrong number of saved prefixes")
            known = []
            ratios = []
            at_five = []
            for rank in range(1, len(row["retrieved"])+1):
                hits, weakest, point_audit = [], [], []
                for index, point in enumerate(q["answers"]):
                    spans = []
                    for e in point["evidence"]:
                        positions = set()
                        for cid in row["retrieved"][:rank]:
                            c = intervals[cid]
                            if c["doc"] == e["doc"]:
                                positions.update(range(max(e["start"],c["start"]), min(e["end"],c["end"])))
                        length, covered = e["end"]-e["start"], len(positions)
                        spans.append({"doc":e["doc"], "start":e["start"], "end":e["end"],
                                      "covered":covered, "length":length, "hit":covered*2>length})
                    hit = all(s["hit"] for s in spans)
                    if hit:
                        hits.append(index)
                    weakest.append(min(s["covered"]/s["length"] for s in spans))
                    point_audit.append({"point_index":index, "hit":hit, "evidence":spans})
                known.append(hits)
                ratios.append(weakest)
                if rank == min(5, len(row["retrieved"])):
                    at_five = point_audit
                if a["hits_by_prefix"][rank-1] != hits:
                    raise ValueError(f"Prefix hit disagreement: {label} {q['id']} rank {rank}")
                for x, y in zip(a["point_coverage_by_prefix"][rank-1], weakest, strict=True):
                    close(x, y)
            recall, complete = {}, {}
            for k in (1,3,5):
                hits = known[min(k,len(known))-1] if known else []
                recall[k] = len(hits)/len(q["answers"]) if q["answers"] else 0.0
                complete[k] = float(evaluated and bool(q["answers"]) and len(hits)==len(q["answers"]))
                close(a["recall_at"][str(k)], recall[k])
                close(a["complete_at"][str(k)], complete[k])
            mrr = next((1/rank for rank,h in enumerate(known,1) if h),0.0)
            close(a["mrr"],mrr)
            independent.append({"q":q,"refused":row["refused"],"recall":recall,"complete":complete,"mrr":mrr})
            audit.append({"config":label,"id":q["id"],"evaluated":evaluated,
                          "status":q["annotation_status"],"rank":min(5,len(row["retrieved"])),
                          "point_evidence_coverage":at_five})
        answerable = [r for r in independent if r["q"]["type"]!="no_answer" and r["q"]["annotation_status"]!="needs_review"]
        no_answer = [r for r in independent if r["q"]["type"]=="no_answer" and r["q"]["annotation_status"]!="needs_review"]
        pending = sum(r["q"]["annotation_status"]=="needs_review" for r in independent)
        assert report["n_answerable"] == len(answerable) and report["n_no_answer"] == len(no_answer)
        assert report["n_queries"] == len(questions) and report["n_pending"] == pending
        close(report["mrr"],sum(r["mrr"] for r in answerable)/len(answerable))
        for k in (1,3,5):
            close(report["recall_at"][str(k)],sum(r["recall"][k] for r in answerable)/len(answerable))
            count = sum(r["complete"][k] for r in answerable)
            close(report["complete_at"][str(k)],count/len(answerable))
            close(report["conservative_complete"]["complete_at"][str(k)],count/(len(answerable)+pending))
        assert report["conservative_complete"]["denominator"] == len(answerable)+pending
        assert report["refusal"]["total"] == len(no_answer)
        assert report["refusal"]["answerable_total"] == len(answerable)
        assert report["refusal"]["correct"] == sum(r["refused"] for r in no_answer)
        assert report["refusal"]["false_refusals"] == sum(r["refused"] for r in answerable)
        close(report["refusal"]["accuracy"],sum(r["refused"] for r in no_answer)/len(no_answer))
        close(report["refusal"]["false_rate"],sum(r["refused"] for r in answerable)/len(answerable))
        verification["configs"][label] = {"query_rows_checked":len(independent),
                                          "saved_report_sha256":digest(saved_path),
                                          "regrade_sha256":digest(DATA / meta["result"]),
                                          "all_prefixes_and_metrics_agree":True}
    audit_path = DATA / "coverage.audit.jsonl"
    audit_path.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in audit)+"\n",encoding="utf-8",newline="\n")
    verification["coverage_audit_sha256"] = digest(audit_path)
    (DATA / "INDEPENDENT_CHECK.json").write_text(json.dumps(verification,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print("Independent character-set check: all 124 query rows, every saved prefix and all summary metrics agree")


if __name__ == "__main__":
    main()
