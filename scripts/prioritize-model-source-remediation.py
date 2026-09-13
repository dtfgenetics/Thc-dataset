#!/usr/bin/env python3
"""Prioritize Grow Doc source-evidence remediation without changing training eligibility.

This helper consumes the existing source-evidence audit and turns its remediation queues
into a deterministic worklist. Priority is operational only: it must never be interpreted
as a truth score, automatic rejection rule, or permission to promote material into SFT.

Operational remediation is grouped by canonical source identity. A single DOI/URL reused
across multiple diagnostic profiles should be reviewed once while preserving every impacted
profile/source occurrence in the worklist.
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
            reasons.append("supports five or more claim bindings across impacted profiles")
            return 1, "P1-general-web-high-impact", reasons
        return 2, "P2-general-web", reasons

    if queue == "missing_year":
        reasons.append("publication year is missing")
        if claims >= 5:
            reasons.append("supports five or more claim bindings across impacted profiles")
            return 2, "P2-missing-year-high-impact", reasons
        return 3, "P3-missing-year", reasons

    if queue == "age_scope":
        reasons.append("source age crossed the review threshold; age alone is not disqualifying")
        age = int(item.get("age_years") or 0)
        if claims >= 5 or age >= 20:
            if claims >= 5:
                reasons.append("supports five or more claim bindings across impacted profiles")
            if age >= 20:
                reasons.append("twenty or more years old")
            return 3, "P3-age-scope-high-impact", reasons
        return 4, "P4-age-scope", reasons

    raise ValueError(f"unsupported remediation queue: {queue}")


def _profile_ref(row: dict) -> dict:
    return {
        "profile_id": row.get("profile_id"),
        "source_index": row.get("source_index"),
        "supported_claims": int(row.get("supported_claims") or 0),
    }


def _merge_source_metadata(existing: dict, row: dict) -> None:
    """Preserve metadata variants so canonical grouping never hides disagreement."""
    for field in ("tier", "year", "title", "organization", "doi", "url"):
        value = row.get(field)
        if value in (None, ""):
            continue
        variants = existing["metadata_variants"].setdefault(field, [])
        if value not in variants:
            variants.append(value)


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
            existing = merged.get(source_id)
            if existing is None:
                existing = {
                    "source_id": source_id,
                    "tier": row.get("tier"),
                    "year": row.get("year"),
                    "title": row.get("title"),
                    "organization": row.get("organization"),
                    "doi": row.get("doi"),
                    "url": row.get("url"),
                    "queues": [],
                    "profile_refs": [],
                    "metadata_variants": {},
                    "_profile_ref_keys": set(),
                    "_max_age_years": 0,
                }
                merged[source_id] = existing

            if queue_name not in existing["queues"]:
                existing["queues"].append(queue_name)

            ref = _profile_ref(row)
            ref_key = (str(ref["profile_id"]), int(ref["source_index"] or 0))
            if ref_key not in existing["_profile_ref_keys"]:
                existing["_profile_ref_keys"].add(ref_key)
                existing["profile_refs"].append(ref)

            existing["_max_age_years"] = max(
                int(existing["_max_age_years"]),
                int(row.get("age_years") or 0),
            )
            _merge_source_metadata(existing, row)

    worklist: list[dict] = []
    for source in merged.values():
        source["profile_refs"].sort(
            key=lambda ref: (str(ref.get("profile_id") or ""), int(ref.get("source_index") or 0))
        )
        supported_claim_bindings = sum(
            int(ref.get("supported_claims") or 0) for ref in source["profile_refs"]
        )
        profile_ids = sorted({str(ref.get("profile_id") or "") for ref in source["profile_refs"]})
        source_occurrences = len(source["profile_refs"])

        candidates = []
        for queue_name in source["queues"]:
            rank, label, reasons = classify(
                {
                    "supported_claims": supported_claim_bindings,
                    "age_years": source["_max_age_years"],
                },
                queue=queue_name,
            )
            candidates.append((rank, label, reasons))
        priority_rank, priority, _ = min(candidates, key=lambda item: item[0])

        priority_reasons: list[str] = []
        for _, _, reasons in candidates:
            for reason in reasons:
                if reason not in priority_reasons:
                    priority_reasons.append(reason)
        if source_occurrences > 1:
            priority_reasons.append(
                f"one canonical source appears in {source_occurrences} profile/source occurrences"
            )

        metadata_conflicts = {
            field: values
            for field, values in sorted(source["metadata_variants"].items())
            if len(values) > 1
        }

        worklist.append(
            {
                "source_id": source["source_id"],
                "tier": source["tier"],
                "year": source["year"],
                "title": source["title"],
                "organization": source["organization"],
                "doi": source["doi"],
                "url": source["url"],
                "queues": source["queues"],
                "priority_rank": priority_rank,
                "priority": priority,
                "priority_reasons": priority_reasons,
                "profile_count": len(profile_ids),
                "profile_ids": profile_ids,
                "source_occurrence_count": source_occurrences,
                "supported_claim_bindings": supported_claim_bindings,
                "max_age_years": int(source["_max_age_years"]),
                "metadata_conflicts": metadata_conflicts,
                "profile_refs": source["profile_refs"],
            }
        )

    worklist.sort(
        key=lambda row: (
            int(row["priority_rank"]),
            -int(row.get("supported_claim_bindings") or 0),
            str(row.get("source_id") or ""),
        )
    )
    counts: dict[str, int] = {}
    for row in worklist:
        counts[row["priority"]] = counts.get(row["priority"], 0) + 1

    return {
        "schema_version": "grow-doc-source-remediation-priority-v2",
        "policy": {
            "purpose": "deterministic review ordering only",
            "grouping": "one remediation task per canonical DOI/URL source identity",
            "preserves_impacted_profile_refs": True,
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
    source_a = "url:https://example.test/a"
    report = {
        "hard_errors": 0,
        "general_web_remediation_queue": [
            {"profile_id": "a", "source_index": 1, "source_id": source_a, "supported_claims": 3},
            {"profile_id": "d", "source_index": 4, "source_id": source_a, "supported_claims": 4},
        ],
        "missing_year_remediation_queue": [
            {"profile_id": "a", "source_index": 1, "source_id": source_a, "supported_claims": 3},
            {"profile_id": "d", "source_index": 4, "source_id": source_a, "supported_claims": 4},
            {"profile_id": "b", "source_index": 2, "source_id": "doi:10.1/example", "supported_claims": 1},
        ],
        "age_scope_review_queue": [
            {"profile_id": "c", "source_index": 1, "source_id": "doi:10.2/old", "supported_claims": 2, "age_years": 24},
        ],
    }
    out = build_worklist(report)
    assert out["schema_version"] == "grow-doc-source-remediation-priority-v2"
    assert out["worklist_count"] == 3
    source = next(row for row in out["worklist"] if row["source_id"] == source_a)
    assert source["priority"] == "P1-general-web-high-impact"
    assert source["queues"] == ["general_web", "missing_year"]
    assert source["profile_count"] == 2
    assert source["source_occurrence_count"] == 2
    assert source["supported_claim_bindings"] == 7
    assert source["profile_ids"] == ["a", "d"]
    assert len(source["profile_refs"]) == 2
    old = next(row for row in out["worklist"] if row["source_id"] == "doi:10.2/old")
    assert old["priority"] == "P3-age-scope-high-impact"
    assert out["policy"]["changes_training_eligibility"] is False

    conflict_report = {
        "hard_errors": 0,
        "general_web_remediation_queue": [],
        "missing_year_remediation_queue": [
            {
                "profile_id": "x",
                "source_index": 1,
                "source_id": source_a,
                "supported_claims": 1,
                "title": "Title A",
            },
            {
                "profile_id": "y",
                "source_index": 1,
                "source_id": source_a,
                "supported_claims": 1,
                "title": "Title B",
            },
        ],
        "age_scope_review_queue": [],
    }
    conflict = build_worklist(conflict_report)["worklist"][0]
    assert conflict["metadata_conflicts"]["title"] == ["Title A", "Title B"]
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
