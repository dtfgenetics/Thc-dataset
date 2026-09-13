#!/usr/bin/env python3
"""Prioritize Grow Doc source-evidence remediation without changing training eligibility.

This helper consumes the existing source-evidence audit and turns its remediation queues
into a deterministic worklist. Priority is operational only: it must never be interpreted
as a truth score, automatic rejection rule, or permission to promote material into SFT.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
AUDIT_PATH = ROOT / "scripts/audit-model-source-evidence-quality.py"


def load_audit_module():
    spec = importlib.util.spec_from_file_location("grow_doc_source_evidence_audit", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load evidence audit: {AUDIT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def classify(item: dict, *, queue: str) -> tuple[int, str, list[str]]:
    """Return (rank, label, reasons); lower rank means earlier review."""
    claims = int(item.get("supported_claims") or 0)
    reasons: list[str] = []

    if queue == "general_web":
        reasons.append("general-web evidence requires explicit review before training use")
        if claims >= 5:
            reasons.append("supports five or more claims")
            return 1, "P1-general-web-high-impact", reasons
        return 2, "P2-general-web", reasons

    if queue == "missing_year":
        reasons.append("publication year is missing")
        if claims >= 5:
            reasons.append("supports five or more claims")
            return 2, "P2-missing-year-high-impact", reasons
        return 3, "P3-missing-year", reasons

    if queue == "age_scope":
        reasons.append("source age crossed the review threshold; age alone is not disqualifying")
        age = int(item.get("age_years") or 0)
        if claims >= 5 or age >= 20:
            if claims >= 5:
                reasons.append("supports five or more claims")
            if age >= 20:
                reasons.append("twenty or more years old")
            return 3, "P3-age-scope-high-impact", reasons
        return 4, "P4-age-scope", reasons

    raise ValueError(f"unsupported remediation queue: {queue}")


def build_worklist(report: dict) -> dict:
    merged: dict[str, dict] = {}
    queue_specs = (
        ("general_web", report.get("general_web_remediation_queue") or []),
        ("missing_year", report.get("missing_year_remediation_queue") or []),
        ("age_scope", report.get("age_scope_review_queue") or []),
    )

    for queue_name, rows in queue_specs:
        for row in rows:
            source_id = str(row.get("source_id") or "missing-provenance")
            key = f"{row.get('profile_id')}::{source_id}::{row.get('source_index')}"
            rank, label, reasons = classify(row, queue=queue_name)
            existing = merged.get(key)
            if existing is None:
                existing = {
                    **row,
                    "queues": [],
                    "priority_rank": rank,
                    "priority": label,
                    "priority_reasons": [],
                }
                merged[key] = existing
            existing["queues"].append(queue_name)
            if rank < int(existing["priority_rank"]):
                existing["priority_rank"] = rank
                existing["priority"] = label
            for reason in reasons:
                if reason not in existing["priority_reasons"]:
                    existing["priority_reasons"].append(reason)

    worklist = sorted(
        merged.values(),
        key=lambda row: (
            int(row["priority_rank"]),
            -int(row.get("supported_claims") or 0),
            str(row.get("profile_id") or ""),
            str(row.get("source_id") or ""),
        ),
    )
    counts: dict[str, int] = {}
    for row in worklist:
        counts[row["priority"]] = counts.get(row["priority"], 0) + 1

    return {
        "schema_version": "grow-doc-source-remediation-priority-v1",
        "policy": {
            "purpose": "deterministic review ordering only",
            "changes_training_eligibility": False,
            "source_age_is_automatic_rejection": False,
            "missing_year_is_automatic_rejection": False,
            "general_web_is_automatic_promotion": False,
            "rag_first": True,
        },
        "hard_errors": int(report.get("hard_errors") or 0),
        "priority_counts": dict(sorted(counts.items())),
        "worklist_count": len(worklist),
        "worklist": worklist,
    }


def self_test() -> None:
    report = {
        "hard_errors": 0,
        "general_web_remediation_queue": [
            {"profile_id": "a", "source_index": 1, "source_id": "url:https://example.test/a", "supported_claims": 7},
        ],
        "missing_year_remediation_queue": [
            {"profile_id": "a", "source_index": 1, "source_id": "url:https://example.test/a", "supported_claims": 7},
            {"profile_id": "b", "source_index": 2, "source_id": "doi:10.1/example", "supported_claims": 1},
        ],
        "age_scope_review_queue": [
            {"profile_id": "c", "source_index": 1, "source_id": "doi:10.2/old", "supported_claims": 2, "age_years": 24},
        ],
    }
    out = build_worklist(report)
    assert out["worklist_count"] == 3
    assert out["worklist"][0]["priority"] == "P1-general-web-high-impact"
    assert out["worklist"][0]["queues"] == ["general_web", "missing_year"]
    assert out["worklist"][1]["priority"] == "P3-age-scope-high-impact"
    assert out["policy"]["changes_training_eligibility"] is False
    print("model source remediation priority self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prioritize Grow Doc source-evidence remediation queues.")
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        audit_module = load_audit_module()
        profiles = audit_module.load_jsonl(args.input)
        report = audit_module.audit(profiles)
        out = build_worklist(report)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    printable = {**out, "worklist": out["worklist"][: max(args.top, 0)]}
    print(json.dumps(printable, indent=2, sort_keys=True))
    if out["hard_errors"]:
        print(f"source remediation priority: FAIL ({out['hard_errors']} evidence hard errors)", file=sys.stderr)
        return 1
    print("source remediation priority: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
