#!/usr/bin/env python3
"""Annotate Grow Doc source-remediation tasks with explicit metadata-review state.

This reporting-only audit joins the canonical remediation worklist to the reviewed
source-metadata ledger. It prevents a publisher-checked but genuinely unresolved source
from being operationally indistinguishable from a source that has never been reviewed.
It never changes training eligibility, scientific claims, or RAG-first policy.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIORITY_PATH = ROOT / "scripts/prioritize-model-source-remediation.py"
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_LEDGER = ROOT / "model_tuning/evidence/source_metadata_reviews_v1.jsonl"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_ledger(path: Path) -> dict[str, dict]:
    reviews: dict[str, dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            row = json.loads(raw)
            source_id = row.get("source_id")
            if not isinstance(source_id, str) or not source_id:
                raise ValueError(f"ledger line {line_no}: missing source_id")
            if source_id in reviews:
                raise ValueError(f"ledger line {line_no}: duplicate source_id {source_id}")
            reviews[source_id] = row
    return reviews


def annotate(worklist_report: dict, reviews: dict[str, dict]) -> dict:
    rows: list[dict] = []
    status_counts: dict[str, int] = {}
    reviewed_in_queue = 0
    unresolved_in_queue = 0

    for item in worklist_report.get("worklist") or []:
        source_id = str(item.get("source_id") or "")
        review = reviews.get(source_id)
        if review is None:
            state = "never-reviewed"
            review_summary = None
            next_action = "perform publisher/DOI metadata review"
        else:
            status = str(review.get("review_status") or "unknown")
            state = status
            reviewed_in_queue += 1
            if status == "verified-unresolved":
                unresolved_in_queue += 1
                next_action = "retain unresolved metadata; recheck only when new publisher evidence appears"
            elif status == "verified-current":
                next_action = "reconcile why a publisher-verified source still appears in a remediation queue"
            else:
                next_action = "review recorded metadata finding before any corpus change"
            review_summary = {
                "checked_date": review.get("checked_date"),
                "review_status": status,
                "publication_date": review.get("publication_date"),
                "year": review.get("year"),
                "finding": review.get("finding"),
                "evidence_scope": review.get("evidence_scope"),
            }

        status_counts[state] = status_counts.get(state, 0) + 1
        rows.append({**item, "metadata_review_state": state, "metadata_review": review_summary, "next_metadata_action": next_action})

    return {
        "schema_version": "grow-doc-source-remediation-review-state-v1",
        "policy": {
            "reporting_only": True,
            "changes_training_eligibility": False,
            "source_age_is_automatic_rejection": False,
            "missing_year_is_automatic_rejection": False,
            "verified_unresolved_is_automatic_rejection": False,
            "rag_first": True,
        },
        "hard_errors": int(worklist_report.get("hard_errors") or 0),
        "worklist_count": len(rows),
        "reviewed_in_queue": reviewed_in_queue,
        "verified_unresolved_in_queue": unresolved_in_queue,
        "never_reviewed_in_queue": status_counts.get("never-reviewed", 0),
        "review_state_counts": dict(sorted(status_counts.items())),
        "worklist": rows,
    }


def self_test() -> None:
    worklist = {
        "hard_errors": 0,
        "worklist": [
            {"source_id": "url:https://example.test/a", "queues": ["missing_year"]},
            {"source_id": "doi:10.1/example", "queues": ["age_scope"]},
        ],
    }
    reviews = {
        "url:https://example.test/a": {
            "source_id": "url:https://example.test/a",
            "checked_date": "2026-09-13",
            "review_status": "verified-unresolved",
            "publication_date": None,
            "year": None,
            "finding": "Publisher exposes no date.",
            "evidence_scope": "publisher-page-metadata",
        }
    }
    out = annotate(worklist, reviews)
    assert out["worklist_count"] == 2
    assert out["reviewed_in_queue"] == 1
    assert out["verified_unresolved_in_queue"] == 1
    assert out["never_reviewed_in_queue"] == 1
    assert out["policy"]["changes_training_eligibility"] is False
    assert out["worklist"][0]["metadata_review_state"] == "verified-unresolved"
    assert out["worklist"][1]["metadata_review_state"] == "never-reviewed"
    print("source remediation review-state self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Join Grow Doc remediation priority to metadata-review state.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        priority = load_module(PRIORITY_PATH, "grow_doc_source_remediation_priority")
        audit = priority.load_audit_module()
        profiles = audit.load_jsonl(args.input)
        worklist = priority.build_worklist(audit.audit(profiles))
        reviews = load_ledger(args.ledger)
        out = annotate(worklist, reviews)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    printable = {**out, "worklist": out["worklist"][: max(args.top, 0)]}
    print(json.dumps(printable, indent=2, sort_keys=True))
    if out["hard_errors"]:
        print(f"source remediation review-state: FAIL ({out['hard_errors']} evidence hard errors)", file=sys.stderr)
        return 1
    print("source remediation review-state: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
