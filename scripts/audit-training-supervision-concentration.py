#!/usr/bin/env python3
"""Measure concentration in the strong-evidence Grow Doc weight-training lane.

This is intentionally report-only. It quantifies whether otherwise unique SFT/grounded-QA
examples are dominated by a small number of canonical sources, diagnostic profiles, or task
families. It does not mutate canonical RAG, delete supervision, or impose an uncalibrated failure
threshold. The report is meant to establish a baseline before any balancing policy is enforced.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
from collections import Counter
from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[1]
ELIGIBLE_BUILDER = ROOT / "scripts/build-training-eligible-supervision.py"


def load_module(path: pathlib.Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ranked(counter: Counter[str], total: int, limit: int = 25) -> list[dict]:
    rows = []
    for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]:
        rows.append({"key": key, "examples": count, "share": round(count / total, 6) if total else 0.0})
    return rows


def audit(records: list[dict]) -> dict:
    source_counts: Counter[str] = Counter()
    profile_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    source_example_counts: Counter[str] = Counter()

    for record in records:
        profile_counts[str(record.get("profile_id") or "<missing-profile>")] += 1
        task_counts[str(record.get("task") or "<missing-task>")] += 1
        source_ids = sorted({str(x) for x in (record.get("source_ids") or []) if str(x).strip()})
        for source_id in source_ids:
            source_counts[source_id] += 1
        if source_ids:
            source_example_counts[source_ids[0]] += 1

    total = len(records)
    unique_sources = len(source_counts)
    source_mentions = sum(source_counts.values())
    top_source_share = max((count / total for count in source_counts.values()), default=0.0)
    top_profile_share = max((count / total for count in profile_counts.values()), default=0.0)
    top_task_share = max((count / total for count in task_counts.values()), default=0.0)

    return {
        "schema_version": "grow-doc-training-supervision-concentration-v1",
        "policy": {
            "scope": "deduplicated strong-evidence training-eligible SFT and grounded-QA candidates",
            "rag_first": True,
            "report_only": True,
            "automatic_rebalancing": False,
            "canonical_rag_mutated": False,
            "failure_threshold": None,
            "purpose": "establish measured source/profile/task concentration before enforcing balancing limits",
        },
        "candidate_examples": total,
        "unique_source_ids": unique_sources,
        "source_mentions": source_mentions,
        "top_source_example_share": round(top_source_share, 6),
        "top_profile_example_share": round(top_profile_share, 6),
        "top_task_example_share": round(top_task_share, 6),
        "sources": ranked(source_counts, total),
        "profiles": ranked(profile_counts, total),
        "tasks": ranked(task_counts, total),
    }


def run() -> dict:
    eligible = load_module(ELIGIBLE_BUILDER, "grow_doc_supervision_concentration_eligible")
    sft, qa, eligibility_report = eligible.run(eligible.DEFAULT_INPUT, eligible.DEFAULT_EVAL)
    report = audit(sft + qa)
    report["eligibility_snapshot"] = {
        "training_eligible_sft_examples": len(sft),
        "training_eligible_grounded_qa_examples": len(qa),
        "exact_supervision_duplicates_excluded_within_task": eligibility_report[
            "exact_supervision_duplicates_excluded"
        ],
    }
    return report


def self_test() -> None:
    records = [
        {"id": "a", "task": "science_education", "profile_id": "p1", "source_ids": ["doi:10.x/a"]},
        {"id": "b", "task": "grounded_qa", "profile_id": "p1", "source_ids": ["doi:10.x/a", "url:https://example.edu/b"]},
        {"id": "c", "task": "grounded_qa", "profile_id": "p2", "source_ids": ["url:https://example.edu/b"]},
        {"id": "d", "task": "grounded_qa", "profile_id": "p3", "source_ids": ["doi:10.x/c"]},
    ]
    report = audit(records)
    assert report["candidate_examples"] == 4
    assert report["unique_source_ids"] == 3
    assert report["top_source_example_share"] == 0.5
    assert report["top_profile_example_share"] == 0.5
    assert report["top_task_example_share"] == 0.75
    assert report["policy"]["report_only"] is True
    print("training supervision concentration self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Grow Doc training supervision concentration.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        report = run()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    print("training supervision concentration audit: PASS (report-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
