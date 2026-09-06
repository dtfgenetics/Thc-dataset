#!/usr/bin/env python3
"""Score the controlled Grow Doc base-only vs frozen-RAG experiment.

Unlike adapter promotion, this comparison EXPECTS retrieval to differ between arms.
Everything else must remain identical: benchmark, model, tokenizer/template, decoding,
scorer revision, and complete recorded runtime. Human-reviewed semantic point scores
remain mandatory; raw model response text is immutable and hash-bound to run manifests.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCORER_PATH = ROOT / "scripts/score-model-eval.py"
# Retrieval is intended to improve factual grounding without sacrificing the core
# behavior/safety contract. Treat all explicitly protected held-out slices as
# fail-closed: an aggregate gain cannot hide a factuality or regression loss.
CRITICAL_SLICES = {"citation_accuracy", "hallucination", "diagnostic", "factuality", "regression"}


def load_scorer():
    spec = importlib.util.spec_from_file_location("grow_doc_model_scorer", SCORER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load scorer: {SCORER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_vs_rag_comparability_errors(base: dict[str, Any], rag: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if base.get("schema_version") != rag.get("schema_version"):
        errors.append("run manifest schema_version differs")

    for section in ("model", "tokenizer", "decoding", "evaluation"):
        if base.get(section) != rag.get(section):
            errors.append(f"{section} differs between base and RAG arms")

    # For this experiment the *only* intended intervention is retrieval.
    if base.get("retrieval") is not None:
        errors.append("base-only arm must have retrieval=null")
    rag_retrieval = rag.get("retrieval")
    if not isinstance(rag_retrieval, dict):
        errors.append("RAG arm must record a frozen retrieval configuration")
    else:
        snapshot = rag_retrieval.get("snapshot_sha256")
        top_k = rag_retrieval.get("top_k")
        if not isinstance(snapshot, str) or len(snapshot) != 64:
            errors.append("RAG arm retrieval snapshot_sha256 must be pinned")
        if not isinstance(top_k, int) or top_k < 1:
            errors.append("RAG arm retrieval top_k must be positive")

    if base.get("runtime") != rag.get("runtime"):
        errors.append("recorded runtime differs between base and RAG arms")
    return errors


def comparison_decision(base_summary: dict[str, Any], rag_summary: dict[str, Any]) -> dict[str, Any]:
    base_agg = (base_summary.get("overall") or {}).get("aggregate")
    rag_agg = (rag_summary.get("overall") or {}).get("aggregate")
    if base_agg is None or rag_agg is None:
        return {
            "review_complete": False,
            "rag_preferred_by_reviewed_metrics": False,
            "reason": "reviewed semantic scores are required",
        }
    gain_pp = round((rag_agg - base_agg) * 100.0, 2)
    regressions: list[dict[str, Any]] = []
    for category in sorted(CRITICAL_SLICES):
        base_value = ((base_summary.get("slices") or {}).get(category) or {}).get("aggregate")
        rag_value = ((rag_summary.get("slices") or {}).get(category) or {}).get("aggregate")
        if base_value is not None and rag_value is not None and rag_value < base_value:
            regressions.append({
                "slice": category,
                "base": base_value,
                "rag": rag_value,
                "delta_pp": round((rag_value - base_value) * 100.0, 2),
            })
    return {
        "review_complete": True,
        "aggregate_gain_pp": gain_pp,
        "critical_regressions": regressions,
        "rag_preferred_by_reviewed_metrics": gain_pp > 0 and not regressions,
        "policy": "RAG preference is descriptive for this base-vs-RAG experiment; it is not an adapter promotion, merge, or deployment decision.",
    }


def score(args: argparse.Namespace) -> dict[str, Any]:
    scorer = load_scorer()
    eval_path = pathlib.Path(args.eval)
    base_review_path = pathlib.Path(args.base_reviewed)
    rag_review_path = pathlib.Path(args.rag_reviewed)
    base_raw_path = pathlib.Path(args.base_raw)
    rag_raw_path = pathlib.Path(args.rag_raw)
    base_manifest_path = pathlib.Path(args.base_manifest)
    rag_manifest_path = pathlib.Path(args.rag_manifest)

    eval_rows = scorer.load_jsonl(eval_path)
    base_reviewed = scorer.load_jsonl(base_review_path)
    rag_reviewed = scorer.load_jsonl(rag_review_path)
    base_raw = scorer.load_jsonl(base_raw_path)
    rag_raw = scorer.load_jsonl(rag_raw_path)
    base_manifest = scorer.load_json(base_manifest_path)
    rag_manifest = scorer.load_json(rag_manifest_path)

    errors: list[str] = []
    errors.extend(scorer.validate_predictions(eval_rows, base_reviewed, True))
    errors.extend(scorer.validate_predictions(eval_rows, rag_reviewed, True))
    errors.extend(base_vs_rag_comparability_errors(base_manifest, rag_manifest))
    errors.extend(scorer.manifest_binding_errors(eval_path, base_raw_path, base_manifest, "base"))
    errors.extend(scorer.manifest_binding_errors(eval_path, rag_raw_path, rag_manifest, "rag"))
    errors.extend(scorer.reviewed_raw_binding_errors(base_reviewed, base_raw, "base"))
    errors.extend(scorer.reviewed_raw_binding_errors(rag_reviewed, rag_raw, "rag"))
    if errors:
        raise ValueError("\n".join(errors))

    base_map = {row["id"]: row for row in base_reviewed}
    rag_map = {row["id"]: row for row in rag_reviewed}
    base_cases = [scorer.score_row(case, base_map[case["id"]], True) for case in eval_rows]
    rag_cases = [scorer.score_row(case, rag_map[case["id"]], True) for case in eval_rows]
    base_summary = scorer.summarize(base_cases)
    rag_summary = scorer.summarize(rag_cases)

    report = {
        "schema_version": "grow-doc-base-vs-rag-reviewed-score-v1",
        "status": "reviewed_comparison",
        "promotion_eligible": False,
        "benchmark_sha256": scorer.sha256_file(eval_path),
        "base": base_summary,
        "rag": rag_summary,
        "comparison": comparison_decision(base_summary, rag_summary),
        "bindings": {
            "base_raw_sha256": scorer.sha256_file(base_raw_path),
            "rag_raw_sha256": scorer.sha256_file(rag_raw_path),
            "base_manifest_sha256": scorer.sha256_file(base_manifest_path),
            "rag_manifest_sha256": scorer.sha256_file(rag_manifest_path),
        },
        "cases": {
            "base": base_cases,
            "rag": rag_cases,
        },
    }
    return report


def self_test() -> None:
    runtime = {"python": "3.12", "torch": "2.14.0", "transformers": "5.16.1", "accelerate": "1.14.0", "peft": "0.20.0", "bitsandbytes": "0.50.2", "device": "cuda", "gpu_name": "fixture"}
    common = {
        "schema_version": "grow-doc-eval-run-v1",
        "model": {"repository": "Qwen/Qwen3-8B", "revision": "a" * 40, "dtype": "bfloat16", "adapter": None},
        "tokenizer": {"repository": "Qwen/Qwen3-8B", "revision": "a" * 40, "chat_template_sha256": "b" * 64, "chat_template_method": "apply_chat_template:add_generation_prompt", "chat_template_kwargs": {"enable_thinking": False}},
        "decoding": {"temperature": 0.0, "top_p": 1.0, "max_new_tokens": 512, "do_sample": False, "seed": 420},
        "evaluation": {"benchmark_path": "heldout.jsonl", "benchmark_sha256": "c" * 64, "scorer_revision": "d" * 40},
        "runtime": runtime,
    }
    base = json.loads(json.dumps(common)); base["retrieval"] = None
    rag = json.loads(json.dumps(common)); rag["retrieval"] = {"snapshot_sha256": "e" * 64, "top_k": 5, "reranker": None}
    assert base_vs_rag_comparability_errors(base, rag) == []

    bad = json.loads(json.dumps(rag)); bad["decoding"]["seed"] = 1
    assert "decoding differs between base and RAG arms" in base_vs_rag_comparability_errors(base, bad)
    bad = json.loads(json.dumps(rag)); bad["runtime"]["torch"] = "different"
    assert "recorded runtime differs between base and RAG arms" in base_vs_rag_comparability_errors(base, bad)
    bad_base = json.loads(json.dumps(base)); bad_base["retrieval"] = {"snapshot_sha256": "f" * 64, "top_k": 5}
    assert "base-only arm must have retrieval=null" in base_vs_rag_comparability_errors(bad_base, rag)

    base_summary = {
        "overall": {"aggregate": 0.70},
        "slices": {
            "diagnostic": {"aggregate": 0.70},
            "citation_accuracy": {"aggregate": 0.70},
            "hallucination": {"aggregate": 0.70},
            "factuality": {"aggregate": 0.70},
            "regression": {"aggregate": 0.70},
        },
    }
    rag_summary = {
        "overall": {"aggregate": 0.75},
        "slices": {
            "diagnostic": {"aggregate": 0.72},
            "citation_accuracy": {"aggregate": 0.80},
            "hallucination": {"aggregate": 0.70},
            "factuality": {"aggregate": 0.76},
            "regression": {"aggregate": 0.70},
        },
    }
    decision = comparison_decision(base_summary, rag_summary)
    assert decision["aggregate_gain_pp"] == 5.0
    assert decision["rag_preferred_by_reviewed_metrics"] is True

    diagnostic_regression = json.loads(json.dumps(rag_summary))
    diagnostic_regression["slices"]["diagnostic"]["aggregate"] = 0.69
    assert comparison_decision(base_summary, diagnostic_regression)["rag_preferred_by_reviewed_metrics"] is False

    factuality_regression = json.loads(json.dumps(rag_summary))
    factuality_regression["slices"]["factuality"]["aggregate"] = 0.69
    factuality_decision = comparison_decision(base_summary, factuality_regression)
    assert factuality_decision["rag_preferred_by_reviewed_metrics"] is False
    assert any(row["slice"] == "factuality" for row in factuality_decision["critical_regressions"])

    regression_slice_loss = json.loads(json.dumps(rag_summary))
    regression_slice_loss["slices"]["regression"]["aggregate"] = 0.69
    regression_decision = comparison_decision(base_summary, regression_slice_loss)
    assert regression_decision["rag_preferred_by_reviewed_metrics"] is False
    assert any(row["slice"] == "regression" for row in regression_decision["critical_regressions"])
    print("base-vs-RAG scorer self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", default="model_tuning/eval/heldout_v2.jsonl")
    parser.add_argument("--base-reviewed")
    parser.add_argument("--rag-reviewed")
    parser.add_argument("--base-raw")
    parser.add_argument("--rag-raw")
    parser.add_argument("--base-manifest")
    parser.add_argument("--rag-manifest")
    parser.add_argument("--out")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    required = (args.base_reviewed, args.rag_reviewed, args.base_raw, args.rag_raw, args.base_manifest, args.rag_manifest)
    if any(value is None for value in required):
        parser.error("base/rag reviewed predictions, raw responses, and run manifests are all required")
    try:
        report = score(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"base-vs-RAG score: FAIL: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
