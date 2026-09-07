#!/usr/bin/env python3
"""Audit Grow Doc source evidence quality without mutating frozen model artifacts.

This is a reporting/validation layer, not an automatic truth score. DOI-backed scholarly
sources, institutional guidance, and general web sources can all be useful for retrieval,
but they should not be treated as interchangeable evidence classes. Source age is reported
for review rather than used as an automatic rejection criterion because older primary work
can remain authoritative.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict
from datetime import date
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
AGE_REVIEW_YEARS = 10


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def hostname(source: dict) -> str:
    value = str(source.get("url") or "").strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    return (parsed.hostname or "").lower()


def evidence_tier(source: dict) -> str:
    """Return a conservative provenance class; this does not assert study quality."""
    if str(source.get("doi") or "").strip():
        return "scholarly_doi"
    host = hostname(source)
    if not host:
        return "missing_provenance"
    institutional_markers = (
        ".gov", ".gov.", ".edu", ".ac.", "canada.ca", "gov.uk", "extension.",
        "usda.gov", "epa.gov", "who.int", "fao.org",
    )
    if any(marker in host for marker in institutional_markers):
        return "institutional_web"
    return "general_web"


def source_year(source: dict) -> int | None:
    raw = source.get("year")
    if raw is None:
        publication = str(source.get("publicationDate") or "")
        raw = publication[:4] if len(publication) >= 4 else None
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def audit(profiles: list[dict], *, current_year: int | None = None) -> dict:
    current_year = current_year or date.today().year
    tiers = Counter()
    reviewed_profile_count = 0
    sources_total = 0
    supported_claims = 0
    age_review = []
    missing_year = 0
    hard_errors = []
    profile_tiers: dict[str, Counter] = defaultdict(Counter)

    for profile in profiles:
        if profile.get("reviewStatus") != "reviewed":
            continue
        reviewed_profile_count += 1
        pid = str(profile.get("id") or "<missing-profile-id>")
        for index, source in enumerate(profile.get("sources") or [], 1):
            sources_total += 1
            tier = evidence_tier(source)
            tiers[tier] += 1
            profile_tiers[pid][tier] += 1
            claims = source.get("supportedClaims") or []
            supported_claims += len(claims)

            if tier == "missing_provenance":
                hard_errors.append(f"{pid}: source {index} is missing DOI/URL provenance")
            if not claims:
                hard_errors.append(f"{pid}: source {index} has no supportedClaims")

            year = source_year(source)
            if year is None:
                missing_year += 1
            elif year > current_year:
                hard_errors.append(f"{pid}: source {index} has future publication year {year}")
            elif current_year - year >= AGE_REVIEW_YEARS:
                age_review.append({
                    "profile_id": pid,
                    "source_index": index,
                    "year": year,
                    "age_years": current_year - year,
                    "tier": tier,
                    "title": source.get("title"),
                    "doi": source.get("doi"),
                    "url": source.get("url"),
                })

    profiles_without_doi = sorted(
        pid for pid, counts in profile_tiers.items() if counts["scholarly_doi"] == 0
    )
    profiles_general_web_only = sorted(
        pid
        for pid, counts in profile_tiers.items()
        if counts["general_web"] > 0
        and counts["scholarly_doi"] == 0
        and counts["institutional_web"] == 0
    )

    return {
        "schema_version": "grow-doc-source-evidence-audit-v1",
        "reviewed_profiles": reviewed_profile_count,
        "sources_audited": sources_total,
        "supported_claims_audited": supported_claims,
        "evidence_tiers": dict(sorted(tiers.items())),
        "policy": {
            "scholarly_doi": "stable scholarly identity; study quality still requires claim-level review",
            "institutional_web": "eligible supporting guidance; do not silently treat as peer-reviewed primary evidence",
            "general_web": "retrieval/support only unless independently reviewed and explicitly justified",
            "source_age": "review flag only; age alone does not invalidate primary evidence",
            "automatic_training_mutation": False,
        },
        "profiles_without_doi": profiles_without_doi,
        "profiles_general_web_only": profiles_general_web_only,
        "missing_publication_year": missing_year,
        "age_review_threshold_years": AGE_REVIEW_YEARS,
        "sources_requiring_age_scope_review": len(age_review),
        "age_scope_review_examples": age_review[:20],
        "hard_errors": len(hard_errors),
        "errors": hard_errors,
    }


def self_test() -> None:
    profiles = [{
        "id": "p1",
        "reviewStatus": "reviewed",
        "sources": [
            {"doi": "10.1234/example", "url": "https://doi.org/10.1234/example", "year": 2025, "supportedClaims": ["a"]},
            {"url": "https://extension.example.edu/guide", "year": 2010, "supportedClaims": ["b"]},
            {"url": "https://example.com/page", "year": 2024, "supportedClaims": ["c"]},
        ],
    }]
    report = audit(profiles, current_year=2026)
    assert report["hard_errors"] == 0
    assert report["evidence_tiers"] == {
        "general_web": 1,
        "institutional_web": 1,
        "scholarly_doi": 1,
    }
    assert report["sources_requiring_age_scope_review"] == 1

    bad = [{"id": "p2", "reviewStatus": "reviewed", "sources": [{"supportedClaims": []}]}]
    assert audit(bad, current_year=2026)["hard_errors"] == 2
    print("model source evidence quality self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Grow Doc model-source evidence quality tiers.")
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        report = audit(load_jsonl(args.input))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["hard_errors"]:
        print(f"model source evidence quality audit: FAIL ({report['hard_errors']} hard errors)", file=sys.stderr)
        return 1
    print("model source evidence quality audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
