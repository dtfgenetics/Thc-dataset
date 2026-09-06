#!/usr/bin/env python3
"""Measure where required held-out sources first appear under the current retriever.

This diagnostic does not alter retrieval, training, or frozen artifacts. Held-out must_cite is
used only after ranking to measure source-recovery depth.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts/build-rag-eval-snapshot.py"
CLAIMS = ROOT / "model_tuning/generated/rag/claims_v1.jsonl"
BENCH = ROOT / "model_tuning/eval/heldout_v2.jsonl"

spec = importlib.util.spec_from_file_location("rag_eval", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("could not load build-rag-eval-snapshot.py")
rag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag)


def main() -> int:
    claims = rag.load_jsonl(CLAIMS)
    cases = rag.load_jsonl(BENCH)
    rag.validate_claims(claims)
    rag.validate_cases(cases)

    print("coverage_by_depth")
    for top_k in (1, 3, 5, 7, 10, 15, 20):
        snapshot = rag.build(claims, cases, top_k, metadata_aware=True)
        coverage = rag.required_source_coverage(cases, snapshot)
        print(f"top_k={top_k} {coverage['hit_cases']}/{coverage['eligible_cases']} missing={','.join(coverage['missing_case_ids'])}")

    print("first_required_source_depth")
    full = rag.build(claims, cases, 20, metadata_aware=True)
    by_case = {row["case_id"]: row for row in full}
    for case in cases:
        required = {str(x).strip() for x in case.get("must_cite") or [] if str(x).strip()}
        if not required:
            continue
        cumulative: set[str] = set()
        found_depth = None
        for item in by_case[case["id"]]["retrieved"]:
            cumulative.update(str(x).strip() for x in item.get("source_ids") or [] if str(x).strip())
            if required.issubset(cumulative):
                found_depth = item["rank"]
                break
        print(json.dumps({"case_id": case["id"], "required_source_depth": found_depth}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
