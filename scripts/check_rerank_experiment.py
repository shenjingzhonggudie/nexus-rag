"""Independently check a completed paired reranking experiment with stdlib only.

Evidence coverage is recomputed with sets of character positions, without
importing the production scorer, retrieval pipeline, models or tensor libraries.
This verifies saved evidence metrics and provenance, not annotation semantics or
semantic answer correctness. Local frozen inputs and index files must remain
available for the provenance/coordinate checks.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
KS = (1, 3, 5)
VARIANTS = ("fusion_only", "cross_encoder")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, label):
    require(isinstance(actual, (int, float)) and not isinstance(actual, bool)
            and math.isfinite(actual)
            and math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12),
            f"Arithmetic disagreement at {label}: {actual!r} != {expected!r}")


def mean(values):
    return sum(values) / len(values) if values else 0.0


def percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    floor = math.floor(position)
    fraction = position - floor
    return ordered[floor] * (1 - fraction) + ordered[min(floor + 1, len(ordered) - 1)] * fraction


def check_local_models(models):
    """Check only local snapshot files; this function cannot download anything."""
    explicit_cache = os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    if explicit_cache:
        cache = Path(explicit_cache).expanduser()
    else:
        default_cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        hf_home = Path(os.environ.get("HF_HOME", default_cache / "huggingface")).expanduser()
        cache = hf_home / "hub"
    checked = {}
    for model_id, model in models.items():
        snapshot = cache / ("models--" + model_id.replace("/", "--")) / "snapshots" / model["revision"]
        require(snapshot.is_dir(), f"Frozen local model snapshot is missing (no download attempted): {snapshot}")
        for filename, expected in model["files"].items():
            path = snapshot / filename
            require(path.is_file(), f"Frozen local model file is missing (no download attempted): {path}")
            require(sha(path) == expected, f"Frozen local model file hash changed: {model_id}/{filename}")
        checked[model_id] = {"revision": model["revision"], "file_count": len(model["files"]),
                             "all_local_file_hashes_agree": True}
    return checked


def check_answer(question, answer, raw, chunks, label):
    """Check the saved extractive response bytes/structure, not their semantics."""
    require(answer["id"] == question["id"] and answer["question"] == question["query"],
            f"Local saved answer ID/query/order mismatch: {label}")
    require(type(answer["refused"]) is bool and answer["refused"] == raw["refused"],
            f"Local saved answer refusal mismatch: {label}")
    require(answer["trace"] == raw["trace"], f"Local saved answer trace mismatch: {label}")
    results = raw["results"]
    if raw["refused"]:
        expected_text, expected_contexts, expected_citations, expected_confidence = "", [], [], 0.0
    else:
        selected = [chunks[result["chunk_id"]] for result in results]
        expected_text = selected[0]["text"]
        expected_contexts = [chunk["text"] for chunk in selected]
        expected_citations = [{"index": index, "source": chunk["source"],
                               "snippet": chunk["text"], "title": chunk.get("title", "")}
                              for index, chunk in enumerate(selected, 1)]
        expected_confidence = results[0]["score"]
    require(answer["answer"] == expected_text and answer["contexts"] == expected_contexts
            and answer["citations"] == expected_citations,
            f"Local saved answer/contexts/citations differ from actual selected blocks: {label}")
    close(answer["confidence"], expected_confidence, f"{label}/saved_answer_confidence")
    require(hashlib.sha256(answer["answer"].encode("utf-8")).hexdigest() == raw["answer_sha256"],
            f"Local saved answer hash differs from archived raw record: {label}")


def point_hits(question, chunks):
    """Use explicit position sets clipped separately to each necessary span."""
    hits, weakest, counts = [], [], []
    for index, point in enumerate(question.get("answers", [])):
        supports = point["evidence"]
        require(bool(supports), f"Empty evidence supports: {question['id']}")
        support_counts = []
        for support in supports:
            start, end = support["start"], support["end"]
            require(type(start) is int and type(end) is int and 0 <= start < end,
                    f"Illegal gold offsets: {question['id']}")
            require(len(support["quote"]) == end - start,
                    f"Gold quote length mismatch: {question['id']}")
            covered_positions = set()
            for chunk in chunks:
                if chunk["doc_id"] == support["doc"]:
                    covered_positions.update(range(max(start, chunk["start"]),
                                                   min(end, chunk["end"])))
            support_counts.append({"covered": len(covered_positions), "length": end - start})
        if all(s["covered"] * 2 > s["length"] for s in support_counts):
            hits.append(index)
        weakest.append(min(s["covered"] / s["length"] for s in support_counts))
        counts.append(support_counts)
    return hits, weakest, counts


def validate_ref(reference, chunks, context):
    chunk_id = reference["chunk_id"]
    require(chunk_id in chunks, f"Unknown chunk ID: {context} {chunk_id}")
    chunk = chunks[chunk_id]
    require(reference["doc_id"] == chunk["doc_id"]
            and reference["start"] == chunk["metadata"]["char_start"]
            and reference["end"] == chunk["metadata"]["char_end"],
            f"Recorded offsets differ from frozen index: {context} {chunk_id}")
    require(type(reference["start"]) is int and type(reference["end"]) is int
            and 0 <= reference["start"] < reference["end"],
            f"Illegal saved offsets: {context} {chunk_id}")
    require(reference["text_sha256"] == hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest(),
            f"Recorded text hash differs from index: {context} {chunk_id}")
    require(isinstance(reference["score"], (int, float))
            and not isinstance(reference["score"], bool) and math.isfinite(reference["score"]),
            f"Illegal score: {context} {chunk_id}")


def check_row(question, row, raw, cfg, chunks, variant):
    label = f"{variant}/{question['id']}"
    require(question["annotation_version"] == 2, f"Non-v2 gold: {label}")
    evaluated = question.get("annotation_status", "complete") != "needs_review"
    no_answer = question["type"] == "no_answer"
    require(row["id"] == raw["id"] == question["id"]
            and row["query"] == raw["query"] == question["query"],
            f"Row ID/query/order mismatch: {label}")
    require(row["annotation_version"] == 2 and row["evaluated"] == evaluated
            and row["is_no_answer"] == no_answer
            and row["source"] == question.get("source", "internal")
            and row["type"] == question["type"]
            and row["point_labels"] == [p["point"] for p in question.get("answers", [])],
            f"Gold/report metadata mismatch: {label}")
    candidates, results = raw["fusion_candidates"], raw["results"]
    require(len(candidates) <= cfg["retrieval"]["top_k"]
            and len(results) == min(len(candidates), cfg["retrieval"]["final_k"]),
            f"Candidate/result limits disagree: {label}")
    for ref in candidates + results:
        validate_ref(ref, chunks, label)
    candidate_ids = [c["chunk_id"] for c in candidates]
    result_ids = [c["chunk_id"] for c in results]
    require(len(set(candidate_ids)) == len(candidate_ids)
            and len(set(result_ids)) == len(result_ids)
            and set(result_ids) <= set(candidate_ids), f"Duplicate/noncandidate output: {label}")
    require(row["retrieved"] == result_ids, f"Report/raw order mismatch: {label}")
    require(all(c["stage"] == "weighted_rrf" for c in candidates), f"Wrong fusion stage: {label}")
    if variant == "fusion_only":
        require(results == candidates[:cfg["retrieval"]["final_k"]], f"Fusion-only truncation changed: {label}")
    else:
        require(all(c["stage"] == "rerank" for c in results), f"Wrong model result stage: {label}")
    require(all(a["score"] >= b["score"] for a, b in zip(results, results[1:])),
            f"Scores not sorted: {label}")
    stages = raw["trace"]["stages"]
    expected_stages = ["bm25", "dense", "fusion"] + (["rerank"] if variant == "cross_encoder" else [])
    require([stage["name"] for stage in stages] == expected_stages, f"Wrong executed stages: {label}")
    require(stages[2]["candidate_count"] == len(candidates), f"Fusion trace count mismatch: {label}")
    if variant == "cross_encoder":
        require(stages[3]["candidate_count"] == len(results), f"Rerank trace count mismatch: {label}")
    for stage in stages:
        require(isinstance(stage["latency_ms"], (int, float))
                and math.isfinite(stage["latency_ms"]) and stage["latency_ms"] >= 0,
                f"Invalid trace latency: {label}")
    close(row["total_ms"], sum(s["latency_ms"] for s in stages), f"{label}/total_ms")
    require(row["match_score"] == raw["match_score"], f"Match score mismatch: {label}")
    threshold = cfg["retrieval"]["refuse_threshold"]
    expected_refused = not results or (threshold > 0 and raw["match_score"] is not None
                                       and raw["match_score"] < threshold)
    require(type(raw["refused"]) is bool and type(row["refused"]) is bool
            and row["refused"] == raw["refused"] == expected_refused,
            f"Refusal disagrees with saved rule inputs: {label}")
    answer_text = "" if expected_refused else chunks[result_ids[0]]["text"]
    require(raw["answer_sha256"] == hashlib.sha256(answer_text.encode("utf-8")).hexdigest()
            and raw["answer_chunk_id"] == (None if expected_refused else result_ids[0]),
            f"Extracted answer hash/ID mismatch: {label}")

    prefixes, weakest_by_prefix, evidence_counts = [], [], []
    for rank in range(1, len(results) + 1):
        hits, ratios, counts = point_hits(question, results[:rank])
        prefixes.append(hits)
        weakest_by_prefix.append(ratios)
        evidence_counts.append(counts)
    require(row["hits_by_prefix"] == prefixes, f"Prefix hit mismatch: {label}")
    require(len(row["point_coverage_by_prefix"]) == len(weakest_by_prefix),
            f"Coverage prefix count mismatch: {label}")
    for rank, (actual, expected) in enumerate(zip(row["point_coverage_by_prefix"], weakest_by_prefix, strict=True), 1):
        require(len(actual) == len(expected), f"Coverage point count mismatch: {label} rank {rank}")
        for index, (a, b) in enumerate(zip(actual, expected, strict=True)):
            close(a, b, f"{label}/coverage/rank{rank}/point{index}")
    single_hits = [point_hits(question, [result])[0] for result in results]
    require(row["hits_per_rank"] == single_hits, f"Single-block hits mismatch: {label}")
    n_points = len(question.get("answers", []))
    recall = {k: len(prefixes[min(k, len(prefixes)) - 1]) / n_points if prefixes and n_points else 0.0 for k in KS}
    # Production retains diagnostics for known points of pending questions here;
    # pending rows are excluded from every main aggregate below.
    complete = {k: float(n_points > 0 and recall[k] == 1.0) for k in KS}
    for k in KS:
        close(row["recall_at"][str(k)], recall[k], f"{label}/recall@{k}")
        close(row["complete_at"][str(k)], complete[k], f"{label}/complete@{k}")
    mrr = next((1 / rank for rank, hit in enumerate(prefixes, 1) if hit), 0.0)
    close(row["mrr"], mrr, f"{label}/mrr")
    return {"id": question["id"], "source": question.get("source", "internal"),
            "evaluated": evaluated, "no_answer": no_answer, "refused": raw["refused"],
            "recall_at": recall, "complete_at": complete, "mrr": mrr,
            "evidence_counts_by_prefix": evidence_counts}


def check_aggregate(report, rows, label):
    answerable = [row for row in rows if row["evaluated"] and not row["no_answer"]]
    no_answer = [row for row in rows if row["evaluated"] and row["no_answer"]]
    pending = [row for row in rows if not row["evaluated"]]
    require(report["n_answerable"] == len(answerable) and report["n_pending"] == len(pending)
            and report["refusal"]["n_no_answer"] == len(no_answer), f"Wrong aggregate denominators: {label}")
    close(report["mrr"], mean([row["mrr"] for row in answerable]), f"{label}/mrr")
    for k in KS:
        close(report["recall_at"][str(k)], mean([row["recall_at"][k] for row in answerable]), f"{label}/recall@{k}")
        close(report["complete_at"][str(k)], mean([row["complete_at"][k] for row in answerable]), f"{label}/complete@{k}")
    close(report["refusal"]["accuracy"], mean([row["refused"] for row in no_answer]), f"{label}/refusal")
    close(report["refusal"]["false_rate"], mean([row["refused"] for row in answerable]), f"{label}/false_refusal")
    sources = {row["source"] for row in answerable}
    require(set(report["by_source"]) == sources, f"Wrong source groups: {label}")
    for source in sources:
        source_rows = [row for row in answerable if row["source"] == source]
        stats = report["by_source"][source]
        require(stats["n"] == len(source_rows), f"Wrong source denominator: {label}/{source}")
        close(stats["mrr"], mean([row["mrr"] for row in source_rows]), f"{label}/{source}/mrr")
        for k in KS:
            close(stats["recall_at"][str(k)], mean([row["recall_at"][k] for row in source_rows]), f"{label}/{source}/recall@{k}")
            close(stats["complete_at"][str(k)], mean([row["complete_at"][k] for row in source_rows]), f"{label}/{source}/complete@{k}")
    return {"query_rows_checked": len(rows), "answerable": len(answerable),
            "no_answer": len(no_answer), "pending": len(pending),
            "correct_refusals": sum(row["refused"] for row in no_answer),
            "false_refusals": sum(row["refused"] for row in answerable),
            "complete_at_5_count": sum(row["complete_at"][5] for row in answerable),
            "conservative_complete_at_5": sum(row["complete_at"][5] for row in answerable) / (len(answerable) + len(pending))
            if answerable or pending else 0.0,
            "all_prefixes_and_metrics_agree": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, help="Completed archive directory")
    args = parser.parse_args()
    archive = Path(args.path).resolve()
    plan = load(archive / "PLAN.json")
    completed = load(archive / "COMPLETED.json")
    require(completed["inputs_unchanged"] and completed["paired_candidate_pools_identical"]
            and completed["refusal_decisions_identical"], "Runner did not complete invariant checks")
    for name, digest in completed["files_sha256"].items():
        require(sha(archive / name) == digest, f"Completed archive hash changed: {name}")
    for name, digest in plan["input_sha256"].items():
        require(sha(ROOT / name) == digest, f"Frozen local input hash changed: {name}")
    require(sha(ROOT / "scripts/run_rerank_experiment.py") == plan["runner_sha256"],
            "Runner differs from frozen copy")
    require(plan["protocol"]["ks"] == list(KS) and plan["protocol"]["variants"] == list(VARIANTS),
            "Unexpected frozen protocol")
    local_answers = ROOT / plan["protocol"]["full_answer_text"]
    expected_answer_files = {f"answers.{dataset}.{variant}.jsonl"
                             for dataset in plan["datasets"] for variant in VARIANTS}
    require(set(completed["local_answer_files_sha256"]) == expected_answer_files,
            "Completed local answer file manifest differs from planned blocks")
    for name, digest in completed["local_answer_files_sha256"].items():
        path = local_answers / name
        require(path.is_file(), f"Saved local answer file is missing: {path}")
        require(sha(path) == digest, f"Completed local answer file hash changed: {name}")
    checked_models = check_local_models(plan["models"])
    configs = {variant: load(archive / f"config.{variant}.json") for variant in VARIANTS}
    off, on = deepcopy(configs["fusion_only"]), deepcopy(configs["cross_encoder"])
    require(off["rerank"]["enabled"] is False and on["rerank"]["enabled"] is True,
            "Rerank switches are not the planned on/off pair")
    off["rerank"]["enabled"] = True
    require(off == on, "Paired configurations differ beyond rerank.enabled")
    index_dir = ROOT / on["index_dir"]
    index_rows = lines(index_dir / "chunks.jsonl")
    chunks = {chunk["chunk_id"]: chunk for chunk in index_rows}
    require(len(chunks) == len(index_rows), "Duplicate chunk IDs in index")
    manifest = load(index_dir / "manifest.json")
    require(manifest["provider"] == "bge" and manifest["model_name"] == on["embedding"]["model_name"],
            "Unexpected actual index provider/model")
    summary = load(archive / "SUMMARY.json")
    check = {"method": "independent_character_position_sets", "production_scorer_imported": False,
             "semantic_answer_correctness_verified": False, "annotation_semantics_verified": False,
             "source_commit": plan["source_commit"], "checker_sha256": sha(__file__),
             "checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
             "plan_sha256": sha(archive / "PLAN.json"), "completed_sha256": sha(archive / "COMPLETED.json"),
             "frozen_local_input_count": len(plan["input_sha256"]),
             "local_models": checked_models,
             "local_answer_files_checked": len(expected_answer_files),
             "saved_answer_structure_verified": True,
             "blocks": {}, "paired_query_count": 0}
    audit_rows = []
    paired_raw = {}
    for dataset, qrels_path in plan["datasets"].items():
        questions = load(ROOT / qrels_path)
        require(len({q["id"] for q in questions}) == len(questions), f"Duplicate gold IDs: {dataset}")
        for variant in VARIANTS:
            label = f"{dataset}.{variant}"
            report_path = archive / f"eval.{label}.json"
            report = load(report_path)
            raw = lines(archive / f"retrievals.{label}.jsonl")
            answers = lines(local_answers / f"answers.{label}.jsonl")
            require(len(report["per_query"]) == len(raw) == len(answers) == len(questions), f"Wrong row count: {label}")
            expected_config = deepcopy(configs[variant])
            expected_config["embedding"]["provider_configured"] = expected_config["embedding"]["provider"]
            require(report["config"] == expected_config, f"Effective config mismatch: {label}")
            require(report["experiment"]["source_commit"] == plan["source_commit"]
                    and report["experiment"]["dataset"] == dataset
                    and report["experiment"]["variant"] == variant, f"Wrong report experiment identity: {label}")
            require(report["scoring"]["annotation_version"] == 2
                    and report["scoring"]["coverage_threshold"] == 0.5
                    and report["scoring"]["comparison"] == ">"
                    and report["scoring"]["union_by_document"] is True,
                    f"Unexpected scoring contract: {label}")
            rows = []
            for question, row, saved, answer in zip(questions, report["per_query"], raw, answers, strict=True):
                independent = check_row(question, row, saved, configs[variant], chunks, variant)
                check_answer(question, answer, saved, chunks, f"{label}/{question['id']}")
                rows.append(independent)
                audit_rows.append({"block": label, **independent})
                key = (dataset, question["id"])
                if variant == "fusion_only":
                    paired_raw[key] = saved
                else:
                    baseline = paired_raw[key]
                    require(saved["fusion_candidates"] == baseline["fusion_candidates"],
                            f"Paired fusion candidates/metadata/scores changed: {label}/{question['id']}")
                    require(saved["match_score"] == baseline["match_score"]
                            and saved["refused"] == baseline["refused"],
                            f"Paired refusal inputs/decision changed: {label}/{question['id']}")
                    check["paired_query_count"] += 1
            check["blocks"][label] = {**check_aggregate(report, rows, label),
                                       "report_sha256": sha(report_path)}
            latency = [row["total_ms"] for row in report["per_query"]]
            close(report["latency"]["cold_ms"], latency[0] if latency else 0.0, f"{label}/first_query_ms")
            close(report["latency"]["warm_mean_ms"], statistics.mean(latency[1:]) if len(latency) > 1 else 0.0,
                  f"{label}/remaining_mean_ms")
            close(report["latency"]["warm_p50_ms"], percentile(latency[1:], 0.5), f"{label}/remaining_p50_ms")
            close(report["latency"]["warm_p95_ms"], percentile(latency[1:], 0.95), f"{label}/remaining_p95_ms")
            require(summary[label] == {k: v for k, v in report.items() if k != "per_query"},
                    f"Summary differs from detailed report: {label}")
    audit_path = archive / "coverage.independent.jsonl"
    audit_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, allow_nan=False) for row in audit_rows)
                          + "\n", encoding="utf-8", newline="\n")
    check["coverage_audit_sha256"] = sha(audit_path)
    check["all_checks_passed"] = True
    (archive / "INDEPENDENT_CHECK.json").write_text(json.dumps(check, ensure_ascii=False, indent=2,
                                                            allow_nan=False) + "\n",
                                                   encoding="utf-8", newline="\n")
    print(f"Independent character-set check passed: {len(audit_rows)} rows, "
          f"{check['paired_query_count']} on/off pairs; all prefixes and aggregate metrics agree")


if __name__ == "__main__":
    main()
