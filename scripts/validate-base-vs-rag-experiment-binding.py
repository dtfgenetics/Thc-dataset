#!/usr/bin/env python3
"""Validate that a Grow Doc base-vs-RAG experiment is cryptographically bound end to end.

This validator does not score model quality. It proves that the top-level experiment
manifest, benchmark, frozen retrieval artifacts, responses, and per-arm run manifests
refer to the exact same evaluation contract before blinded review/scoring is trusted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "grow-doc-base-vs-rag-experiment-v4"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def require_hex(value: Any, length: int, label: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(c not in "0123456789abcdef" for c in value.lower()):
        raise ValueError(f"{label} must be {length} hexadecimal characters")
    return value.lower()


def require_hash(path: Path, expected: Any, label: str) -> None:
    want = require_hex(expected, 64, label)
    got = sha256(path)
    if got != want:
        raise ValueError(f"{label} mismatch: expected {want}, got {got}")


def validate(
    experiment_path: Path,
    benchmark_path: Path,
    retrieval_snapshot_path: Path,
    retrieval_manifest_path: Path,
    base_responses_path: Path,
    base_run_manifest_path: Path,
    rag_responses_path: Path,
    rag_run_manifest_path: Path,
) -> dict[str, Any]:
    exp = load_json(experiment_path)
    base = load_json(base_run_manifest_path)
    rag = load_json(rag_run_manifest_path)
    retrieval_manifest = load_json(retrieval_manifest_path)

    errors: list[str] = []
    if exp.get("schema_version") != EXPECTED_SCHEMA:
        errors.append(f"experiment schema must be {EXPECTED_SCHEMA}")
    if exp.get("status") != "pending_review":
        errors.append("experiment status must remain pending_review before blinded scoring")
    if exp.get("promotion_eligible") is not False:
        errors.append("raw base-vs-RAG experiment must not be promotion eligible")

    repo_revision = exp.get("repo_revision")
    try:
        require_hex(repo_revision, 40, "repo_revision")
    except ValueError as exc:
        errors.append(str(exc))

    benchmark = exp.get("benchmark") or {}
    retrieval = exp.get("retrieval") or {}
    arms = exp.get("arms") or {}
    base_arm = arms.get("base_only") or {}
    rag_arm = arms.get("base_plus_rag") or {}

    for path, expected, label in [
        (benchmark_path, benchmark.get("sha256"), "benchmark sha256"),
        (retrieval_snapshot_path, retrieval.get("snapshot_sha256"), "retrieval snapshot sha256"),
        (retrieval_manifest_path, retrieval.get("manifest_sha256"), "retrieval manifest sha256"),
        (base_responses_path, base_arm.get("responses_sha256"), "base responses sha256"),
        (base_run_manifest_path, base_arm.get("run_manifest_sha256"), "base run-manifest sha256"),
        (rag_responses_path, rag_arm.get("responses_sha256"), "RAG responses sha256"),
        (rag_run_manifest_path, rag_arm.get("run_manifest_sha256"), "RAG run-manifest sha256"),
    ]:
        try:
            require_hash(path, expected, label)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))

    snapshot_hash = sha256(retrieval_snapshot_path)
    benchmark_hash = sha256(benchmark_path)
    if retrieval_manifest.get("snapshot_sha256") != snapshot_hash:
        errors.append("retrieval manifest is not bound to the supplied snapshot")
    if retrieval_manifest.get("benchmark_sha256") != benchmark_hash:
        errors.append("retrieval manifest is not bound to the supplied benchmark")
    top_k = retrieval_manifest.get("top_k")
    if type(top_k) is not int or top_k < 1:
        errors.append("retrieval manifest top_k must be a positive integer")
    if not isinstance(retrieval_manifest.get("algorithm"), str) or not retrieval_manifest.get("algorithm"):
        errors.append("retrieval manifest algorithm must be recorded")

    for label, manifest in (("base", base), ("RAG", rag)):
        evaluation = manifest.get("evaluation") or {}
        if evaluation.get("benchmark_sha256") != benchmark_hash:
            errors.append(f"{label} run manifest benchmark hash differs from experiment benchmark")
        if evaluation.get("scorer_revision") != repo_revision:
            errors.append(f"{label} scorer revision differs from experiment repo revision")

    comparable_sections = ("model", "tokenizer", "decoding", "runtime")
    for section in comparable_sections:
        if base.get(section) != rag.get(section):
            errors.append(f"{section} differs between base and RAG run manifests")

    if base.get("retrieval") is not None:
        errors.append("base run manifest must record retrieval=null")
    rag_retrieval = rag.get("retrieval")
    if not isinstance(rag_retrieval, dict):
        errors.append("RAG run manifest must record retrieval configuration")
    else:
        if rag_retrieval.get("snapshot_sha256") != snapshot_hash:
            errors.append("RAG run manifest snapshot hash differs from frozen retrieval snapshot")
        if rag_retrieval.get("top_k") != top_k:
            errors.append("RAG run manifest top_k differs from frozen retrieval manifest")

    exp_model = exp.get("model") or {}
    base_model = base.get("model") or {}
    if exp_model.get("repository") != base_model.get("repository") or exp_model.get("revision") != base_model.get("revision"):
        errors.append("experiment model identity differs from per-arm run manifests")

    exp_tokenizer = exp.get("tokenizer") or {}
    base_tokenizer = base.get("tokenizer") or {}
    if exp_tokenizer.get("revision") != base_tokenizer.get("revision"):
        errors.append("experiment tokenizer revision differs from per-arm run manifests")
    if exp_tokenizer.get("chat_template_sha256") != base_tokenizer.get("chat_template_sha256"):
        errors.append("experiment chat-template hash differs from per-arm run manifests")

    if exp.get("decoding") != base.get("decoding"):
        errors.append("experiment decoding contract differs from per-arm run manifests")

    if errors:
        raise ValueError("\n".join(errors))

    return {
        "schema_version": "grow-doc-base-vs-rag-binding-validation-v1",
        "status": "pass",
        "promotion_eligible": False,
        "repo_revision": repo_revision,
        "benchmark_sha256": benchmark_hash,
        "retrieval_snapshot_sha256": snapshot_hash,
        "retrieval_manifest_sha256": sha256(retrieval_manifest_path),
        "retrieval_algorithm": retrieval_manifest["algorithm"],
        "top_k": top_k,
        "base_responses_sha256": sha256(base_responses_path),
        "rag_responses_sha256": sha256(rag_responses_path),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        benchmark = root / "heldout.jsonl"
        snapshot = root / "snapshot.jsonl"
        retrieval_manifest_path = root / "snapshot.manifest.json"
        base_responses = root / "base.responses.jsonl"
        rag_responses = root / "rag.responses.jsonl"
        base_run_path = root / "base.run.json"
        rag_run_path = root / "rag.run.json"
        experiment_path = root / "experiment.json"

        benchmark.write_text('{"id":"case-1"}\n', encoding="utf-8")
        snapshot.write_text('{"case_id":"case-1","retrieved":[]}\n', encoding="utf-8")
        base_responses.write_text('{"id":"case-1","response":"base"}\n', encoding="utf-8")
        rag_responses.write_text('{"id":"case-1","response":"rag"}\n', encoding="utf-8")
        write_json(retrieval_manifest_path, {
            "schema_version": "grow-doc-rag-snapshot-v2",
            "algorithm": "fixture-retrieval-v1",
            "top_k": 5,
            "benchmark_sha256": sha256(benchmark),
            "snapshot_sha256": sha256(snapshot),
        })
        runtime = {"device": "cuda", "gpu_name": "fixture", "torch": "2.14.0"}
        model = {"repository": "Qwen/Qwen3-8B", "revision": "a" * 40, "dtype": "bfloat16", "adapter": None}
        tokenizer = {"repository": "Qwen/Qwen3-8B", "revision": "a" * 40, "chat_template_sha256": "b" * 64, "chat_template_method": "apply_chat_template:add_generation_prompt", "chat_template_kwargs": {"enable_thinking": False}}
        decoding = {"do_sample": False, "temperature": 0.0, "top_p": 1.0, "max_new_tokens": 512, "seed": 420}
        evaluation = {"benchmark_path": "heldout.jsonl", "benchmark_sha256": sha256(benchmark), "scorer_revision": "c" * 40}
        base = {"schema_version": "grow-doc-eval-run-v1", "model": model, "tokenizer": tokenizer, "decoding": decoding, "evaluation": evaluation, "runtime": runtime, "retrieval": None}
        rag = json.loads(json.dumps(base)); rag["retrieval"] = {"snapshot_sha256": sha256(snapshot), "top_k": 5, "reranker": None}
        write_json(base_run_path, base); write_json(rag_run_path, rag)
        experiment = {
            "schema_version": EXPECTED_SCHEMA,
            "status": "pending_review",
            "promotion_eligible": False,
            "repo_revision": "c" * 40,
            "model": {"repository": "Qwen/Qwen3-8B", "revision": "a" * 40},
            "tokenizer": {"revision": "a" * 40, "chat_template_sha256": "b" * 64, "enable_thinking": False},
            "decoding": decoding,
            "benchmark": {"path": "heldout.jsonl", "sha256": sha256(benchmark)},
            "retrieval": {"snapshot_path": "snapshot.jsonl", "snapshot_sha256": sha256(snapshot), "manifest_path": "snapshot.manifest.json", "manifest_sha256": sha256(retrieval_manifest_path)},
            "arms": {
                "base_only": {"responses_sha256": sha256(base_responses), "run_manifest_sha256": sha256(base_run_path)},
                "base_plus_rag": {"responses_sha256": sha256(rag_responses), "run_manifest_sha256": sha256(rag_run_path)},
            },
        }
        write_json(experiment_path, experiment)
        report = validate(experiment_path, benchmark, snapshot, retrieval_manifest_path, base_responses, base_run_path, rag_responses, rag_run_path)
        assert report["status"] == "pass"
        assert report["retrieval_algorithm"] == "fixture-retrieval-v1"

        bad = json.loads(json.dumps(experiment)); bad["retrieval"]["manifest_sha256"] = "0" * 64
        write_json(experiment_path, bad)
        try:
            validate(experiment_path, benchmark, snapshot, retrieval_manifest_path, base_responses, base_run_path, rag_responses, rag_run_path)
        except ValueError as exc:
            assert "retrieval manifest sha256 mismatch" in str(exc)
        else:
            raise AssertionError("mutated retrieval-manifest binding must fail")

        write_json(experiment_path, experiment)
        bad_rag = json.loads(json.dumps(rag)); bad_rag["retrieval"]["top_k"] = 4
        write_json(rag_run_path, bad_rag)
        experiment["arms"]["base_plus_rag"]["run_manifest_sha256"] = sha256(rag_run_path)
        write_json(experiment_path, experiment)
        try:
            validate(experiment_path, benchmark, snapshot, retrieval_manifest_path, base_responses, base_run_path, rag_responses, rag_run_path)
        except ValueError as exc:
            assert "top_k differs" in str(exc)
        else:
            raise AssertionError("run/manifest retrieval-contract drift must fail")
    print("base-vs-RAG experiment binding self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--experiment", type=Path)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--retrieval-snapshot", type=Path)
    parser.add_argument("--retrieval-manifest", type=Path)
    parser.add_argument("--base-responses", type=Path)
    parser.add_argument("--base-run-manifest", type=Path)
    parser.add_argument("--rag-responses", type=Path)
    parser.add_argument("--rag-run-manifest", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    required = [args.experiment, args.benchmark, args.retrieval_snapshot, args.retrieval_manifest, args.base_responses, args.base_run_manifest, args.rag_responses, args.rag_run_manifest]
    if any(value is None for value in required):
        parser.error("all experiment, benchmark, retrieval, response, and run-manifest paths are required")
    try:
        report = validate(args.experiment, args.benchmark, args.retrieval_snapshot, args.retrieval_manifest, args.base_responses, args.base_run_manifest, args.rag_responses, args.rag_run_manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"base-vs-RAG experiment binding: FAIL: {exc}")
        return 2
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
