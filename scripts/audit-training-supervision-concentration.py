#!/usr/bin/env python3
"""Measure concentration and drift in the strong-evidence Grow Doc weight-training lane.

This remains report-only. It quantifies whether otherwise unique SFT/grounded-QA examples are
concentrated in a small number of canonical sources, diagnostic profiles, or task families and,
when a frozen baseline is present, reports deltas against that baseline. It does not mutate
canonical RAG, delete supervision, rebalance examples, or impose an uncalibrated failure threshold.
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
DEFAULT_BASELINE = ROOT / "model_tuning/training-supervision-concentration-baseline.json"


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

    for record in records:
        profile_counts[str(record.get("profile_id") or "<missing-profile>")] += 1
        task_counts[str(record.get("task") or "<missing-task>")] += 1
        source_ids = sorted({str(x) for x in (record.get("source_ids") or []) if str(x).strip()})
        for source_id in source_ids:
            source_counts[source_id] += 1

    total = len(records)
    return {
        "schema_version": "grow-doc-training-supervision-concentration-v2",
        "policy": {
            "scope": "deduplicated strong-evidence training-eligible SFT and grounded-QA candidates",
            "rag_first": True,
            "report_only": True,
            "automatic_rebalancing": False,
            "canonical_rag_mutated": False,
            "failure_threshold": None,
            "purpose": "measure concentration and drift before enforcing balancing limits",
        },
        "candidate_examples": total,
        "unique_source_ids": len(source_counts),
        "source_mentions": sum(source_counts.values()),
        "top_source_example_share": round(max((c / total for c in source_counts.values()), default=0.0), 6),
        "top_profile_example_share": round(max((c / total for c in profile_counts.values()), default=0.0), 6),
        "top_task_example_share": round(max((c / total for c in task_counts.values()), default=0.0), 6),
        "sources": ranked(source_counts, total),
        "profiles": ranked(profile_counts, total),
        "tasks": ranked(task_counts, total),
    }


def load_baseline(path: pathlib.Path) -> dict | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "grow-doc-training-supervision-concentration-baseline-v1":
        raise ValueError(f"unsupported concentration baseline schema: {data.get('schema_version')}")
    return data


def add_baseline_comparison(report: dict, baseline: dict | None) -> None:
    if baseline is None:
        report["baseline_comparison"] = {"available": False}
        return

    metrics = (
        "candidate_examples",
        "unique_source_ids",
        "source_mentions",
        "top_source_example_share",
        "top_profile_example_share",
        "top_task_example_share",
    )
    deltas = {}
    for key in metrics:
        current = report[key]
        previous = baseline[key]
        delta = current - previous
        deltas[key] = round(delta, 6) if isinstance(delta, float) else delta

    current_tasks = {row["key"]: row["share"] for row in report.get("tasks", [])}
    baseline_tasks = baseline.get("task_distribution", {})
    task_deltas = {
        key: round(current_tasks.get(key, 0.0) - float(previous), 6)
        for key, previous in sorted(baseline_tasks.items())
    }
    report["baseline_comparison"] = {
        "available": True,
        "baseline_commit": baseline.get("baseline_commit"),
        "artifact_sha256": (baseline.get("artifact") or {}).get("sha256"),
        "regression_thresholds_enforced": False,
        "metric_deltas": deltas,
        "task_share_deltas": task_deltas,
    }


def run(baseline_path: pathlib.Path = DEFAULT_BASELINE) -> dict:
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
    add_baseline_comparison(report, load_baseline(baseline_path))
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
    baseline = {
        "baseline_commit": "abc",
        "artifact": {"sha256": "deadbeef"},
        "candidate_examples": 3,
        "unique_source_ids": 2,
        "source_mentions": 3,
        "top_source_example_share": 0.4,
        "top_profile_example_share": 0.5,
        "top_task_example_share": 0.7,
        "task_distribution": {"grounded_qa": 0.7},
    }
    add_baseline_comparison(report, baseline)
    assert report["baseline_comparison"]["metric_deltas"]["candidate_examples"] == 1
    assert report["baseline_comparison"]["metric_deltas"]["top_source_example_share"] == 0.1
    assert report["baseline_comparison"]["task_share_deltas"]["grounded_qa"] == 0.05
    assert report["policy"]["report_only"] is True
    print("training supervision concentration self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Grow Doc training supervision concentration and drift.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--baseline", type=pathlib.Path, default=DEFAULT_BASELINE)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        report = run(args.baseline)
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    print("training supervision concentration audit: PASS (report-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
