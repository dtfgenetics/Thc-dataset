#!/usr/bin/env python3
"""Audit freshness of mutable web evidence without treating publication age as truth decay.

Scholarly DOI evidence is intentionally excluded from access-date gating: old primary work can
remain authoritative. This audit focuses on mutable institutional/general web pages whose content
can change or disappear after review. It never upgrades evidence automatically.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from datetime import date, datetime
from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
EVIDENCE_AUDIT = ROOT / "scripts/audit-model-source-evidence-quality.py"
REVIEW_AFTER_DAYS = 365
TRAINING_HOLD_AFTER_DAYS = 730


def load_module(path: pathlib.Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_accessed_date(value: object) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def audit(profiles: list[dict], evidence, *, today: date | None = None) -> dict:
    today = today or date.today()
    mutable_sources = 0
    institutional_sources = 0
    general_web_sources = 0
    missing_accessed_date = []
    invalid_accessed_date = []
    stale_review = []
    training_revalidation_holds = []
    hard_errors = []

    for profile in profiles:
        if profile.get("reviewStatus") != "reviewed":
            continue
        profile_id = str(profile.get("id") or "<missing-profile-id>")
        for source_index, source in enumerate(profile.get("sources") or [], 1):
            tier = evidence.evidence_tier(source)
            if tier not in {"institutional_web", "general_web"}:
                continue
            mutable_sources += 1
            institutional_sources += int(tier == "institutional_web")
            general_web_sources += int(tier == "general_web")
            source_id = evidence.canonical_source_id(source)
            raw_accessed = str(source.get("accessedDate") or "").strip()
            accessed = parse_accessed_date(raw_accessed)
            item = {
                "profile_id": profile_id,
                "source_index": source_index,
                "source_id": source_id,
                "tier": tier,
                "title": source.get("title"),
                "url": source.get("url"),
                "accessed_date": raw_accessed or None,
            }

            if not raw_accessed:
                missing_accessed_date.append(item)
                if tier == "institutional_web":
                    hard_errors.append(f"{profile_id}: institutional source {source_index} lacks accessedDate")
                    training_revalidation_holds.append({**item, "reason": "missing_accessed_date"})
                continue
            if accessed is None:
                invalid_accessed_date.append(item)
                if tier == "institutional_web":
                    hard_errors.append(
                        f"{profile_id}: institutional source {source_index} has invalid accessedDate {raw_accessed!r}"
                    )
                    training_revalidation_holds.append({**item, "reason": "invalid_accessed_date"})
                continue
            if accessed > today:
                hard_errors.append(
                    f"{profile_id}: source {source_index} has future accessedDate {accessed.isoformat()}"
                )
                training_revalidation_holds.append({**item, "reason": "future_accessed_date"})
                continue

            age_days = (today - accessed).days
            if age_days >= REVIEW_AFTER_DAYS:
                stale_review.append({**item, "age_days": age_days})
            if tier == "institutional_web" and age_days >= TRAINING_HOLD_AFTER_DAYS:
                training_revalidation_holds.append(
                    {**item, "age_days": age_days, "reason": "institutional_web_revalidation_overdue"}
                )

    key = lambda row: (row["profile_id"], row["source_id"], row["source_index"])
    missing_accessed_date.sort(key=key)
    invalid_accessed_date.sort(key=key)
    stale_review.sort(key=lambda row: (-row.get("age_days", 0), *key(row)))
    training_revalidation_holds.sort(key=key)

    return {
        "schema_version": "grow-doc-web-source-revalidation-audit-v1",
        "as_of": today.isoformat(),
        "policy": {
            "rag_first": True,
            "scope": "mutable institutional/general web evidence only; DOI-backed scholarly evidence is excluded",
            "review_after_days": REVIEW_AFTER_DAYS,
            "institutional_training_hold_after_days": TRAINING_HOLD_AFTER_DAYS,
            "stale_behavior": "review queue; age alone does not invalidate supported claims",
            "institutional_missing_or_invalid_accessed_date": "hard error and training revalidation hold",
            "general_web_missing_or_invalid_accessed_date": "retrieval remediation queue; not training eligible under the strong-evidence lane",
            "automatic_truth_mutation": False,
        },
        "mutable_web_sources_audited": mutable_sources,
        "institutional_web_sources": institutional_sources,
        "general_web_sources": general_web_sources,
        "missing_accessed_date": len(missing_accessed_date),
        "missing_accessed_date_queue": missing_accessed_date,
        "invalid_accessed_date": len(invalid_accessed_date),
        "invalid_accessed_date_queue": invalid_accessed_date,
        "stale_sources_requiring_review": len(stale_review),
        "stale_review_queue": stale_review,
        "training_revalidation_holds": len(training_revalidation_holds),
        "training_revalidation_hold_queue": training_revalidation_holds,
        "hard_errors": len(hard_errors),
        "errors": hard_errors,
    }


def self_test() -> None:
    class Evidence:
        @staticmethod
        def evidence_tier(source: dict) -> str:
            return str(source["tier"])

        @staticmethod
        def canonical_source_id(source: dict) -> str:
            return str(source["id"])

    profiles = [{
        "id": "p1",
        "reviewStatus": "reviewed",
        "sources": [
            {"tier": "scholarly_doi", "id": "doi:x", "accessedDate": "2010-01-01"},
            {"tier": "institutional_web", "id": "url:edu-fresh", "accessedDate": "2026-01-01"},
            {"tier": "institutional_web", "id": "url:edu-stale", "accessedDate": "2023-01-01"},
            {"tier": "general_web", "id": "url:web-missing"},
        ],
    }]
    report = audit(profiles, Evidence, today=date(2026, 9, 9))
    assert report["mutable_web_sources_audited"] == 3
    assert report["institutional_web_sources"] == 2
    assert report["general_web_sources"] == 1
    assert report["missing_accessed_date"] == 1
    assert report["hard_errors"] == 0
    assert report["stale_sources_requiring_review"] == 1
    assert report["training_revalidation_holds"] == 1
    assert report["training_revalidation_hold_queue"][0]["source_id"] == "url:edu-stale"

    bad = [{
        "id": "p2",
        "reviewStatus": "reviewed",
        "sources": [
            {"tier": "institutional_web", "id": "url:missing"},
            {"tier": "institutional_web", "id": "url:invalid", "accessedDate": "09/09/2026"},
            {"tier": "general_web", "id": "url:future", "accessedDate": "2027-01-01"},
        ],
    }]
    bad_report = audit(bad, Evidence, today=date(2026, 9, 9))
    assert bad_report["hard_errors"] == 3
    assert bad_report["training_revalidation_holds"] == 3
    print("model web-source revalidation self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit mutable Grow Doc web-source revalidation freshness.")
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        evidence = load_module(EVIDENCE_AUDIT, "grow_doc_web_revalidation_evidence")
        if args.self_test:
            self_test()
            return 0
        profiles = evidence.load_jsonl(args.input)
        report = audit(profiles, evidence)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["hard_errors"]:
        print(
            f"model web-source revalidation audit: FAIL ({report['hard_errors']} hard errors)",
            file=sys.stderr,
        )
        return 1
    print("model web-source revalidation audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
