#!/usr/bin/env python3
"""Enrich Grow Doc semantic-redundancy review with source provenance.

This companion audit does not mutate or delete supervision. It reuses the conservative
same-task/different-profile redundancy detector, then records the source identities behind each
near-duplicate pair so reviewers can distinguish repeated evidence from independently supported
but linguistically similar supervision.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[1]
REDUNDANCY_AUDIT = ROOT / "scripts/audit-training-supervision-redundancy.py"
ELIGIBLE_BUILDER = ROOT / "scripts/build-training-eligible-supervision.py"


def load_module(path: pathlib.Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_ids(record: dict) -> list[str]:
    return sorted({str(value).strip() for value in (record.get("source_ids") or []) if str(value).strip()})


def enrich(report: dict, records: list[dict]) -> dict:
    by_id = {str(record.get("id") or "<missing-id>"): source_ids(record) for record in records}
    enriched = []
    same_source_pairs = 0
    independent_source_pairs = 0
    for pair in report.get("near_duplicate_review_queue") or []:
        row = dict(pair)
        left = by_id.get(str(pair.get("left_id")), [])
        right = by_id.get(str(pair.get("right_id")), [])
        shared = sorted(set(left) & set(right))
        row["left_source_ids"] = left
        row["right_source_ids"] = right
        row["shared_source_ids"] = shared
        row["source_relationship"] = "shared_source" if shared else "independent_sources"
        if shared:
            same_source_pairs += 1
        else:
            independent_source_pairs += 1
        enriched.append(row)

    output = dict(report)
    output["schema_version"] = "grow-doc-training-supervision-source-overlap-v1"
    output["near_duplicate_review_queue"] = enriched
    output["near_duplicate_source_summary"] = {
        "shared_source_pairs": same_source_pairs,
        "independent_source_pairs": independent_source_pairs,
        "pairs_missing_source_metadata": sum(
            1 for row in enriched if not row["left_source_ids"] or not row["right_source_ids"]
        ),
    }
    return output


def run(threshold: float) -> dict:
    redundancy = load_module(REDUNDANCY_AUDIT, "grow_doc_source_overlap_redundancy")
    eligible = load_module(ELIGIBLE_BUILDER, "grow_doc_source_overlap_eligible")
    sft, qa, _ = eligible.run(eligible.DEFAULT_INPUT, eligible.DEFAULT_EVAL)
    records = sft + qa
    return enrich(redundancy.audit(records, threshold=threshold), records)


def self_test() -> None:
    base = {
        "near_duplicate_review_queue": [
            {"task": "science_education", "left_id": "a", "right_id": "b", "token_jaccard": 0.9},
            {"task": "diagnostic_reasoning", "left_id": "c", "right_id": "d", "token_jaccard": 0.85},
        ]
    }
    records = [
        {"id": "a", "source_ids": ["doi:10.x/one"]},
        {"id": "b", "source_ids": ["doi:10.x/one", "doi:10.x/two"]},
        {"id": "c", "source_ids": ["doi:10.x/three"]},
        {"id": "d", "source_ids": ["url:https://example.edu/four"]},
    ]
    report = enrich(base, records)
    queue = report["near_duplicate_review_queue"]
    assert queue[0]["shared_source_ids"] == ["doi:10.x/one"]
    assert queue[0]["source_relationship"] == "shared_source"
    assert queue[1]["shared_source_ids"] == []
    assert queue[1]["source_relationship"] == "independent_sources"
    assert report["near_duplicate_source_summary"]["shared_source_pairs"] == 1
    assert report["near_duplicate_source_summary"]["independent_source_pairs"] == 1
    assert report["near_duplicate_source_summary"]["pairs_missing_source_metadata"] == 0
    print("training supervision source-overlap self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Add source provenance to Grow Doc redundancy review.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.82)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not 0.0 < args.threshold <= 1.0:
        print("ERROR: --threshold must be in (0, 1]", file=sys.stderr)
        return 2
    try:
        report = run(args.threshold)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    if report.get("hard_errors"):
        print("training supervision source-overlap: FAIL (upstream exact duplicates)", file=sys.stderr)
        return 1
    print("training supervision source-overlap: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
