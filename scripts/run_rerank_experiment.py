"""Run a fixed, paired fusion/CrossEncoder experiment without changing gold labels.

Reports contain retrieval evidence metrics, not semantic answer correctness.
The previously used holdout is a regression set. Full extracted answer text stays
under ignored reports/; the archive contains IDs, offsets, scores and hashes.
"""

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "dev": "data/eval/qrels.json",
    "holdout_regression": "experiments/holdout-evidence-v2/qrels.v2.json",
}
KS = (1, 3, 5)


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8").strip()


def files_under(paths):
    return {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p)
            for directory in paths for p in sorted(directory.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def chunk_ref(sc):
    chunk = sc.chunk
    return {"chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id,
            "start": chunk.metadata["char_start"],
            "end": chunk.metadata["char_end"],
            "text_sha256": hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
            "score": sc.score, "stage": sc.stage, "sub_scores": sc.sub_scores}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="New archive directory; must not exist")
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()
    if args.threads < 1:
        raise ValueError("threads must be positive")
    os.chdir(ROOT)
    # Freeze offline CPU execution before importing torch/transformers.
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["MKL_NUM_THREADS"] = str(args.threads)
    archive = Path(args.out).resolve()
    archive.mkdir(parents=True, exist_ok=False)
    local = ROOT / "reports" / archive.name
    local.mkdir(parents=True, exist_ok=False)

    import torch
    from huggingface_hub import snapshot_download
    from ragkit.config import load_config
    from ragkit.evaluation import load_qrels
    from ragkit.evaluation import report as report_module
    from ragkit.generation.answer import answer_question
    from ragkit.index import load_index
    from ragkit.loaders import load_file
    from ragkit.text import normalize_text
    import ragkit.retrieval.pipeline as pipeline

    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    # Do not use ambient RAG__ overrides. Pin every effective default in files.
    cfg = load_config(ROOT / "configs/default.yaml", environ={})
    cfg.embedding.provider = "bge"
    assert cfg.retrieval.fusion_method == "weighted_rrf"
    assert cfg.retrieval.fusion_alpha == 0.7
    assert cfg.retrieval.top_k == 20 and cfg.retrieval.final_k == 5
    assert cfg.rerank.enabled and cfg.rerank.device == "cpu"
    assert cfg.rerank.local_files_only and cfg.llm.provider == "none"
    if git("diff", "HEAD", "--", "src", "configs"):
        raise ValueError("Commit production source/config changes before this experiment")
    datasets = {key: load_qrels(ROOT / path) for key, path in DATASETS.items()}
    assert len(datasets["dev"]) == 248 and len(datasets["holdout_regression"]) == 62
    manifest = json.loads((cfg.index_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider"] == "bge" and manifest["model_name"] == cfg.embedding.model_name
    models = {}
    for model_id in (cfg.embedding.model_name, cfg.rerank.model_name):
        download_args = {}
        if model_id == cfg.rerank.model_name:
            download_args["allow_patterns"] = [
                "config.json", "model.safetensors", "sentencepiece.bpe.model",
                "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json",
            ]
        snapshot = Path(snapshot_download(repo_id=model_id, local_files_only=True, **download_args))
        models[model_id] = {"revision": snapshot.name,
                            "files": {str(p.relative_to(snapshot)).replace("\\", "/"): sha(p)
                                      for p in sorted(snapshot.rglob("*")) if p.is_file()}}
    inputs = files_under([ROOT / "src", ROOT / "configs", ROOT / cfg.index_dir,
                          ROOT / cfg.data_dir])
    inputs.update({path: sha(ROOT / path) for path in DATASETS.values()})
    plan = {
        "started_at": now(), "source_commit": git("rev-parse", "HEAD"),
        "initial_git_status": git("status", "--short"),
        "runner_sha256": sha(__file__), "datasets": DATASETS,
        "protocol": {
            "variants": ["fusion_only", "cross_encoder"],
            "only_difference": "rerank.enabled",
            "no_gold_changes_or_parameter_search": True,
            "retrieval_inputs": "query_only; gold evidence is used solely by scoring",
            "holdout_status": "previously_used_regression_not_independent_blind_test",
            "coverage": "union within document; every necessary span strictly >50%",
            "metrics": "macro answer-point recall, first-supported-point prefix MRR, complete coverage",
            "not_measured": "semantic answer correctness or new independent generalization",
            "ks": KS, "pending": "excluded from main metrics and refusal denominators",
            "latency": "single sequential CPU run; trace sums; first query per block is not necessarily a true cold start",
            "full_answer_text": str(local.relative_to(ROOT)).replace("\\", "/"),
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "cpu": platform.processor(), "logical_cpus": os.cpu_count(),
                        "torch_threads": torch.get_num_threads(),
                        "torch_interop_threads": torch.get_num_interop_threads(),
                        "packages": {p: version(p) for p in ("ragkit", "torch", "sentence-transformers",
                                                            "transformers", "huggingface-hub", "numpy")}},
        "models": models, "input_sha256": inputs,
    }
    configs = {}
    for variant in plan["protocol"]["variants"]:
        variant_cfg = cfg.model_copy(deep=True)
        variant_cfg.rerank.enabled = variant == "cross_encoder"
        configs[variant] = variant_cfg
        write(archive / f"config.{variant}.json", variant_cfg.snapshot())
    write(archive / "PLAN.json", plan)
    print("PLAN FROZEN: labels/config/models/index hashes saved; no tuning", flush=True)

    # Verify gold coordinates against current normalized corpus before inference.
    texts = {}
    for qrels in datasets.values():
        assert len({q.id for q in qrels}) == len(qrels)
        for q in qrels:
            assert q.annotation_version == 2
            for evidence in q.answers:
                if evidence.doc not in texts:
                    texts[evidence.doc] = normalize_text(load_file(cfg.data_dir / evidence.doc).text)
                if texts[evidence.doc][evidence.start:evidence.end] != evidence.quote:
                    raise ValueError(f"Gold/corpus mismatch: {q.id}")
    built = load_index(cfg.index_dir, provider=cfg.embedding.provider,
                       model_name=cfg.embedding.model_name)
    for chunk in built.id_to_chunk.values():
        if chunk.doc_id not in texts:
            texts[chunk.doc_id] = normalize_text(load_file(cfg.data_dir / chunk.doc_id).text)
        if texts[chunk.doc_id][chunk.metadata["char_start"]:chunk.metadata["char_end"]] != chunk.text:
            raise ValueError(f"Index/corpus mismatch: {chunk.chunk_id}")
    print(f"INPUTS VERIFIED: {len(texts)} documents, {len(built.id_to_chunk)} chunks", flush=True)

    original_search = report_module.search
    original_fusion = pipeline.weighted_rrf_fuse
    fused = []

    def capture_fusion(*a, **kw):
        result = original_fusion(*a, **kw)
        fused[:] = result
        return result

    pipeline.weighted_rrf_fuse = capture_fusion
    baseline_candidates = {}
    baseline_refusals = {}
    summaries = {}
    try:
        for variant, variant_cfg in configs.items():
            for dataset, qrels in datasets.items():
                name = f"{dataset}.{variant}"
                started = time.perf_counter()
                completed = 0
                last_progress = started
                print(f"START {name}: {len(qrels)} queries", flush=True)
                with (archive / f"retrievals.{name}.jsonl").open("w", encoding="utf-8") as raw, \
                     (local / f"answers.{name}.jsonl").open("w", encoding="utf-8") as answers:

                    def observed_search(query, **kwargs):
                        nonlocal completed, last_progress
                        qrel = qrels[completed]
                        assert query == qrel.query
                        fused.clear()
                        result = original_search(query, **kwargs)
                        answer = answer_question(query, result, llm=variant_cfg.llm,
                                                 refuse_threshold=variant_cfg.retrieval.refuse_threshold)
                        ids = [sc.chunk.chunk_id for sc in fused]
                        key = (dataset, qrel.id)
                        if variant == "fusion_only":
                            baseline_candidates[key] = ids
                            baseline_refusals[key] = answer.refused
                            assert [sc.chunk.chunk_id for sc in result.results] == ids[:5]
                        else:
                            assert ids == baseline_candidates[key], "Paired candidate pool changed"
                            assert answer.refused == baseline_refusals[key], "Independent refusal unexpectedly changed"
                            assert all(sc.stage == "rerank" for sc in result.results)
                            assert set(sc.chunk.chunk_id for sc in result.results) <= set(ids)
                        record = {"id": qrel.id, "query": query, "match_score": result.match_score,
                                  "refused": answer.refused, "trace": result.trace.to_dict(),
                                  "fusion_candidates": [chunk_ref(sc) for sc in fused],
                                  "results": [chunk_ref(sc) for sc in result.results],
                                  "answer_sha256": hashlib.sha256(answer.answer.encode("utf-8")).hexdigest(),
                                  "answer_chunk_id": None if answer.refused else result.results[0].chunk.chunk_id}
                        raw.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                        raw.flush()
                        answers.write(json.dumps({"id": qrel.id, **answer.to_dict()},
                                                 ensure_ascii=False, allow_nan=False) + "\n")
                        answers.flush()
                        completed += 1
                        elapsed = time.perf_counter() - started
                        write(archive / "PROGRESS.json", {"block": name, "completed": completed,
                              "total": len(qrels), "elapsed_seconds": elapsed, "updated_at": now()})
                        if completed == 1 or completed % 10 == 0 or time.perf_counter() - last_progress >= 25:
                            print(f"PROGRESS {name}: {completed}/{len(qrels)} elapsed={elapsed:.1f}s", flush=True)
                            last_progress = time.perf_counter()
                        return result

                    report_module.search = observed_search
                    report = report_module.evaluate(built, variant_cfg, qrels, ks=KS).to_dict()
                assert completed == len(qrels)
                report["experiment"] = {"dataset": dataset, "variant": variant,
                                        "source_commit": plan["source_commit"],
                                        "wall_seconds": time.perf_counter() - started,
                                        "started_at": plan["started_at"], "completed_at": now(),
                                        "first_query_is_true_cold": dataset == "dev",
                                        "note": "Metrics measure retrieved evidence, not semantic answer correctness"}
                write(archive / f"eval.{name}.json", report)
                summaries[name] = {k: v for k, v in report.items() if k != "per_query"}
                # Keep results hidden until both fixed configurations complete.
                print(f"FINISHED {name}; metrics saved", flush=True)
    finally:
        report_module.search = original_search
        pipeline.weighted_rrf_fuse = original_fusion
    changed = [path for path, digest in inputs.items() if sha(ROOT / path) != digest]
    if changed or sha(__file__) != plan["runner_sha256"]:
        raise ValueError(f"Experiment inputs changed during execution: {changed}")
    write(archive / "SUMMARY.json", summaries)
    write(archive / "COMPLETED.json", {"completed_at": now(), "inputs_unchanged": True,
          "paired_candidate_pools_identical": True, "refusal_decisions_identical": True,
          "files_sha256": {p.name: sha(p) for p in sorted(archive.iterdir()) if p.is_file()},
          "local_answer_files_sha256": {p.name: sha(p) for p in sorted(local.iterdir()) if p.is_file()}})
    print(f"ALL COMPLETED: {archive}", flush=True)


if __name__ == "__main__":
    main()
