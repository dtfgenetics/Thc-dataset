#!/usr/bin/env python3
"""Fail closed when reviewed Grow Doc profiles lack training-grade evidence support.

This validator does not mutate the corpus. General-web sources may remain available to RAG,
but a reviewed profile must have at least one DOI-backed scholarly or institutional source
before it is eligible to pass the model-training evidence gate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from types import ModuleType, SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
AUDIT_PATH = ROOT / "scripts/audit-model-source-evidence-quality.py"
STRONG_TIERS = {"scholarly_doi", "institutional_web"}


def load_audit_module(path: pathlib.Path = AUDIT_PATH) -> ModuleType:
    spec = importlib.util.spec_from_file_location("grow_doc_source_evidence_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load evidence audit module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(profiles: list[dict], audit_module) -> dict:
    reviewed_ids: list[str] = []
    source_less: list[str] = []
    weak_only: list[str] = []
    strong_count = 0
    tier_counts: dict[str, int] = {
        "scholarly_doi": 0,
        "institutional_web": 0,
        "general_web": 0,
        "missing_provenance": 0,
    }

    for profile in profiles:
        if profile.get("reviewStatus") != "reviewed":
            continue
        pid = str(profile.get("id") or "<missing-profile-id>")
        reviewed_ids.append(pid)
        sources = profile.get("sources") or []
        if not sources:
            source_less.append(pid)
            continue

        tiers = [audit_module.evidence_tier(source) for source in sources]
        for tier in tiers:
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        if any(tier in STRONG_TIERS for tier in tiers):
            strong_count += 1
        else:
            weak_only.append(pid)

    source_less.sort()
    weak_only.sort()
    errors = [f"{pid}: reviewed profile has no sources" for pid in source_less]
    errors.extend(
        f"{pid}: reviewed profile has no DOI-backed or institutional source; "
        "general-web-only evidence is retrieval/support only"
        for pid in weak_only
    )

    return {
        "schema_version": "grow-doc-training-evidence-eligibility-v1",
        "policy": {
            "training_grade_profile_requires": "at least one scholarly_doi or institutional_web source",
            "general_web": (
                "may remain available for retrieval/support but cannot be the sole evidence class "
                "for a reviewed training-grade profile"
            ),
            "automatic_training_mutation": False,
        },
        "reviewed_profiles": len(reviewed_ids),
        "reviewed_profiles_with_strong_evidence": strong_count,
        "source_tiers_seen": dict(sorted(tier_counts.items())),
        "source_less_reviewed_profiles": source_less,
        "general_web_only_reviewed_profiles": weak_only,
        "hard_errors": len(errors),
        "errors": errors,
    }


def self_test() -> None:
    def tier(source: dict) -> str:
        return str(source["tier"])

    audit_module = SimpleNamespace(evidence_tier=tier)
    good = [
        {
            "id": "doi-backed",
            "reviewStatus": "reviewed",
            "sources": [{"tier": "scholarly_doi"}, {"tier": "general_web"}],
        },
        {
            "id": "institutional",
            "reviewStatus": "reviewed",
            "sources": [{"tier": "institutional_web"}],
        },
        {"id": "draft", "reviewStatus": "draft", "sources": []},
    ]
    report = evaluate(good, audit_module)
    assert report["hard_errors"] == 0
    assert report["reviewed_profiles"] == 2
    assert report["reviewed_profiles_with_strong_evidence"] == 2

    bad = [
        {
            "id": "web-only",
            "reviewStatus": "reviewed",
            "sources": [{"tier": "general_web"}],
        },
        {"id": "none", "reviewStatus": "reviewed", "sources": []},
    ]
    report = evaluate(bad, audit_module)
    assert report["hard_errors"] == 2
    assert report["general_web_only_reviewed_profiles"] == ["web-only"]
    assert report["source_less_reviewed_profiles"] == ["none"]
    print("model training evidence eligibility self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate training-grade evidence eligibility for reviewed Grow Doc profiles."
    )
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        audit_module = load_audit_module()
        profiles = audit_module.load_jsonl(args.input)
        report = evaluate(profiles, audit_module)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["hard_errors"]:
        print(
            f"model training evidence eligibility: FAIL ({report['hard_errors']} hard errors)",
            file=sys.stderr,
        )
        return 1
    print("model training evidence eligibility: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
