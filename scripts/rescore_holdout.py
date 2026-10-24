"""Regrade saved holdout retrievals after checking the committed annotation freeze.

No search, embedding, reranking or generation is run. Existing outputs stay fixed.
"""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from ragkit.chunking.ids import make_chunk_id
from ragkit.evaluation import load_qrels
from ragkit.evaluation.replay import rescore_saved_results
from ragkit.index.chunks_store import read_chunks
from ragkit.loaders import load_file
from ragkit.text import normalize_text


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "experiments/holdout-evidence-v2"
ARCHIVE = ROOT / "experiments/holdout-v1"
FREEZE_COMMIT = "b63d485ab21a882093433e0d62021acb33e28c35"
ORIGINAL_CODE = "80b6aea3da638057db4e531f05e5bedde14f956c"


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def dump(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def archive_payload(path: Path) -> bytes:
    """Read an archived input only if its actual bytes match the frozen Git blob."""
    payload = path.read_bytes()
    relative = path.relative_to(ROOT).as_posix()
    if payload != git("show", f"{FREEZE_COMMIT}:{relative}"):
        raise ValueError(f"Archived file differs from frozen bytes: {relative}")
    return payload


def main() -> None:
    freeze_path = DEST / "ANNOTATION_FREEZE.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    git("merge-base", "--is-ancestor", FREEZE_COMMIT, "HEAD")
    for name, key in (("qrels.v2.json", "qrels_sha256"),
                      ("annotation_review.jsonl", "review_sha256"),
                      ("PROTOCOL.md", "protocol_sha256"),
                      ("ANNOTATION_FREEZE.json", None)):
        payload = (DEST / name).read_bytes()
        if key and sha(payload) != freeze[key]:
            raise ValueError(f"Frozen {name} hash mismatch")
        committed = git("show", f"{FREEZE_COMMIT}:experiments/holdout-evidence-v2/{name}")
        if payload != committed:
            raise ValueError(f"Frozen {name} differs from pre-output commit")
    archive_tree = git("ls-tree", "-r", "HEAD", "--", "experiments/holdout-v1").decode("utf-8")
    if archive_tree != freeze["archive_git_tree"]:
        raise ValueError("Original archive tree changed")
    if git("status", "--porcelain", "--untracked-files=all", "--", "experiments/holdout-v1").strip():
        raise ValueError("Original archive has working-tree changes")
    pipeline_diff = git("diff", "--name-only", f"{ORIGINAL_CODE}..{FREEZE_COMMIT}", "--",
                        "src/ragkit/chunking", "src/ragkit/loaders", "src/ragkit/text", "src/ragkit/schemas.py")
    if pipeline_diff.strip():
        raise ValueError("Historical source-coordinate pipeline changed; cannot assume old chunk mapping")

    corpus = {}
    for doc, expected in freeze["corpus_sha256"].items():
        text = normalize_text(load_file(ROOT / "data/raw" / doc).text)
        if sha(text.encode("utf-8")) != expected:
            raise ValueError(f"Corpus hash mismatch: {doc}")
        corpus[doc] = text
    for rel, expected in freeze["index_file_sha256"].items():
        if sha((ROOT / rel.replace("\\", "/")).read_bytes()) != expected:
            raise ValueError(f"Index changed since annotation start: {rel}")
    qrels = load_qrels(DEST / "qrels.v2.json")
    for q in qrels:
        for evidence in q.answers:
            if corpus[evidence.doc][evidence.start:evidence.end] != evidence.quote:
                raise ValueError(f"Evidence quote mismatch: {q.id}")

    access = json.loads((DEST / "OUTPUT_ACCESS.json").read_text(encoding="utf-8"))
    if access["annotation_freeze_commit"] != FREEZE_COMMIT or access["qrels_sha256"] != freeze["qrels_sha256"]:
        raise ValueError("Output access record does not match annotation freeze")
    original_hashes = {r["path"].replace("\\", "/"):r["sha256"] for r in access["files"]}
    manifest = {
        "rescored_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "annotation_freeze_commit": FREEZE_COMMIT,
        "original_experiment_code": ORIGINAL_CODE,
        "qrels_sha256": freeze["qrels_sha256"],
        "output_access_sha256": sha((DEST / "OUTPUT_ACCESS.json").read_bytes()),
        "source_pipeline_diff_empty": True,
        "normalized_documents_verified": len(corpus),
        "model_rerun": False,
        "actual_answer_text_available": False,
        "score_scope": "saved_retrieval_evidence_coverage_not_final_answer_correctness",
        "scorer_canonical_lf_sha256": sha((ROOT / "src/ragkit/evaluation/replay.py").read_bytes().replace(b"\r\n", b"\n")),
        "script_canonical_lf_sha256": sha(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "configs": {},
    }
    intervals = {}
    for label, saved_name, config_name, index_dir in (
        ("A", "eval.configA.bge.weighted.json", "configA.bge.weighted.yaml", "data/index"),
        ("B", "eval.configB.hashing.rrf.json", "configB.hashing.rrf.yaml", "data/index.hashing"),
    ):
        saved_path = ARCHIVE / "audit" / saved_name
        payload = archive_payload(saved_path)
        relative = saved_path.relative_to(ROOT).as_posix()
        if sha(payload) != original_hashes[relative]:
            raise ValueError(f"Saved report changed since first access: {saved_name}")
        saved = json.loads(payload)
        if any("answer" in r or "answer_text" in r for r in saved["per_query"]):
            raise ValueError("Report contains answer text; update scope explicitly before grading it")
        chunk_path = ROOT / index_dir / "chunks.jsonl"
        chunk_rows = read_chunks(chunk_path)
        chunks = {c.chunk_id:c for c in chunk_rows}
        if len(chunks) != len(chunk_rows):
            raise ValueError("Duplicate IDs in chunk table")
        used = {cid for r in saved["per_query"] for cid in r["retrieved"]}
        for cid in used:
            if cid not in chunks:
                raise ValueError(f"Unresolvable saved chunk: {cid}")
            c = chunks[cid]
            start, end = c.metadata.get("char_start"), c.metadata.get("char_end")
            if type(start) is not int or type(end) is not int or not 0 <= start < end:
                raise ValueError(f"Invalid saved chunk offsets: {cid}")
            if corpus[c.doc_id][start:end] != c.text:
                raise ValueError(f"Chunk differs from archived normalized source: {cid}")
            occurrence = int(cid.rsplit("@", 1)[1])
            if make_chunk_id(c.doc_id, c.text, occurrence) != cid:
                raise ValueError(f"Chunk ID content fingerprint mismatch: {cid}")
            record = {"doc":c.doc_id, "start":start, "end":end,
                      "text_sha256":sha(c.text.encode("utf-8"))}
            if cid in intervals and intervals[cid] != record:
                raise ValueError(f"Chunk maps differently across configurations: {cid}")
            intervals[cid] = record
        report = rescore_saved_results(qrels, saved["per_query"], chunks)
        config_path = ARCHIVE / "audit/frozen_configs" / config_name
        config = yaml.safe_load(archive_payload(config_path).decode("utf-8"))
        report["provenance"] = {
            "annotation_freeze_commit":FREEZE_COMMIT, "qrels_sha256":freeze["qrels_sha256"],
            "saved_report":relative, "saved_report_sha256":sha(payload),
            "chunk_table_sha256":sha(chunk_path.read_bytes()),
            "config_declared_in_archive":config,
            "config_limit":"Original report has no embedded effective-config snapshot; configuration label comes from archived YAML.",
            "model_rerun":False, "actual_answer_text_available":False,
        }
        out = DEST / f"rescore.config{label}.json"
        dump(out, report)
        manifest["configs"][label] = {**report["provenance"], "result":out.name,
                                       "result_sha256":sha(out.read_bytes()), "retrieved_unique_chunks_verified":len(used)}
        print(json.dumps({"config":label, **{k:report[k] for k in
                         ("n_queries", "n_answerable", "n_no_answer", "n_pending", "recall_at", "mrr", "complete_at", "refusal", "conservative_complete")}}, ensure_ascii=False))
    dump(DEST / "retrieved_intervals.json", dict(sorted(intervals.items())))
    manifest["retrieved_intervals_sha256"] = sha((DEST / "retrieved_intervals.json").read_bytes())
    dump(DEST / "RESCORE_MANIFEST.json", manifest)


if __name__ == "__main__":
    main()
