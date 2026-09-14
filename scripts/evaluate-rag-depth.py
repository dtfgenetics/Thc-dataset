#!/usr/bin/env python3
"""Measure and gate required-source recovery under the current frozen retriever.

This evaluation does not alter retrieval, training, or frozen artifacts. Held-out `must_cite`
labels are used only after ranking to measure source-recovery depth. The canonical heldout-v2
contract currently requires complete required-source recovery by top-k=5; this turns the
previous report-only diagnostic into a regression gate for retrieval changes and corpus edits.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts/build-rag-eval-snapshot.py"
CLAIMS = ROOT / "model_tuning/generated/rag/claims_v1.jsonl"
BENCH = ROOT / "model_tuning/eval/heldout_v2.jsonl"
DEPTHS = (1, 3, 5, 7, 10, 15, 20)
REQUIRED_COMPLETE_DEPTH = 5

spec = importlib.util.spec_from_file_location("rag_eval", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("could not load build-rag-eval-snapshot.py")
rag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag)


def measure_depths(claims, cases):
    results = {}
    for top_k in DEPTHS:
        snapshot = rag.build(claims, cases, top_k, metadata_aware=True)
        results[top_k] = rag.required_source_coverage(cases, snapshot)
    return results


def enforce_required_depth(results) -> None:
    coverage = results[REQUIRED_COMPLETE_DEPTH]
    eligible = coverage["eligible_cases"]
    hit = coverage["hit_cases"]
    missing = coverage["missing_case_ids"]
    if eligible <= 0:
        raise SystemExit("heldout benchmark has no must_cite cases; required-source gate cannot run")
    if hit != eligible:
        raise SystemExit(
            "required-source retrieval regression at top-k="
            f"{REQUIRED_COMPLETE_DEPTH}: {hit}/{eligible}; missing={','.join(missing)}"
        )


def self_test() -> None:
    complete = {
        depth: {
            "eligible_cases": 2,
            "hit_cases": 2 if depth >= REQUIRED_COMPLETE_DEPTH else 1,
            "hit_rate": 1.0 if depth >= REQUIRED_COMPLETE_DEPTH else 0.5,
            "missing_case_ids": [] if depth >= REQUIRED_COMPLETE_DEPTH else ["case-b"],
        }
        for depth in DEPTHS
    }
    enforce_required_depth(complete)

    regressed = {depth: dict(values) for depth, values in complete.items()}
    regressed[REQUIRED_COMPLETE_DEPTH] = {
        "eligible_cases": 2,
        "hit_cases": 1,
        "hit_rate": 0.5,
        "missing_case_ids": ["case-b"],
    }
    try:
        enforce_required_depth(regressed)
    except SystemExit as exc:
        assert "required-source retrieval regression" in str(exc)
    else:
        raise AssertionError("top-k=5 required-source regression must fail")
    print("RAG depth regression gate self-test: PASS")


def main() -> int:
    claims = rag.load_jsonl(CLAIMS)
    cases = rag.load_jsonl(BENCH)
    rag.validate_claims(claims)
    rag.validate_cases(cases)

    results = measure_depths(claims, cases)
    print("coverage_by_depth")
    for top_k in DEPTHS:
        coverage = results[top_k]
        print(
            f"top_k={top_k} {coverage['hit_cases']}/{coverage['eligible_cases']} "
            f"missing={','.join(coverage['missing_case_ids'])}"
        )

    enforce_required_depth(results)

    print("first_required_source_depth")
    full = rag.build(claims, cases, 20, metadata_aware=True)
    by_case = {row["case_id"]: row for row in full}
    for case in cases:
        required = {rag.canonical_source_id(x) for x in case.get("must_cite") or [] if rag.canonical_source_id(x)}
        if not required:
            continue
        cumulative: set[str] = set()
        found_depth = None
        for item in by_case[case["id"]]["retrieved"]:
            cumulative.update(
                rag.canonical_source_id(x)
                for x in item.get("source_ids") or []
                if rag.canonical_source_id(x)
            )
            if required.issubset(cumulative):
                found_depth = item["rank"]
                break
        print(json.dumps({"case_id": case["id"], "required_source_depth": found_depth}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
