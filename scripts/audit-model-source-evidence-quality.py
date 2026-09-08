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
from urllib.parse import urlsplit, urlunsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
AGE_REVIEW_YEARS = 10

# These non-.edu/.gov hosts are explicitly verified institutional/Extension publication
# surfaces. Keep this list narrow and evidence-based rather than inferring authority from
# arbitrary organization strings.
VERIFIED_INSTITUTIONAL_HOSTS = {
    "pnwhandbooks.org",
    "www.pnwhandbooks.org",
    "onspecialtycrops.ca",
    "www.onspecialtycrops.ca",
}

# Some universities serve PDFs through third-party/CDN hosts. In those cases, require an
# explicit institutional publisher/organization identity in the source metadata.
VERIFIED_INSTITUTIONAL_ORG_MARKERS = (
    "cornell university",
    "ontario ministry of agriculture",
    "pacific northwest pest management handbooks",
    "pacific northwest plant disease management handbook",
)


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


def canonical_source_id(source: dict) -> str:
    """Return a stable review identifier without asserting source equivalence beyond DOI/URL identity."""
    doi = str(source.get("doi") or "").strip().lower()
    doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:")
    if doi:
        return f"doi:{doi}"
    raw_url = str(source.get("url") or "").strip()
    if not raw_url:
        return "missing-provenance"
    parsed = urlsplit(raw_url)
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/") or "/"
    canonical = urlunsplit((scheme, host + port, path, parsed.query, ""))
    return f"url:{canonical}"


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
    if host in VERIFIED_INSTITUTIONAL_HOSTS:
        return "institutional_web"

    attribution = " ".join(
        str(source.get(field) or "").strip().lower()
        for field in ("organization", "publisher")
    )
    if any(marker in attribution for marker in VERIFIED_INSTITUTIONAL_ORG_MARKERS):
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


def remediation_item(profile_id: str, source_index: int, source: dict, tier: str, year: int | None) -> dict:
    return {
        "profile_id": profile_id,
        "source_index": source_index,
        "source_id": canonical_source_id(source),
        "tier": tier,
        "year": year,
        "title": source.get("title"),
        "organization": source.get("organization"),
        "doi": source.get("doi"),
        "url": source.get("url"),
        "supported_claims": len(source.get("supportedClaims") or []),
    }


def audit(profiles: list[dict], *, current_year: int | None = None) -> dict:
    current_year = current_year or date.today().year
    tiers = Counter()
    reviewed_profile_count = 0
    sources_total = 0
    supported_claims = 0
    age_review = []
    general_web_review = []
    missing_year_review = []
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
            item = remediation_item(pid, index, source, tier, year)
            if tier == "general_web":
                general_web_review.append(item)
            if year is None:
                missing_year += 1
                missing_year_review.append(item)
            elif year > current_year:
                hard_errors.append(f"{pid}: source {index} has future publication year {year}")
            elif current_year - year >= AGE_REVIEW_YEARS:
                age_review.append({**item, "age_years": current_year - year})

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

    general_web_review.sort(key=lambda row: (row["profile_id"], row["source_id"], row["source_index"]))
    missing_year_review.sort(key=lambda row: (row["profile_id"], row["source_id"], row["source_index"]))
    age_review.sort(key=lambda row: (-row["age_years"], row["profile_id"], row["source_id"]))

    return {
        "schema_version": "grow-doc-source-evidence-audit-v3",
        "reviewed_profiles": reviewed_profile_count,
        "sources_audited": sources_total,
        "supported_claims_audited": supported_claims,
        "evidence_tiers": dict(sorted(tiers.items())),
        "policy": {
            "scholarly_doi": "stable scholarly identity; study quality still requires claim-level review",
            "institutional_web": "eligible supporting guidance; do not silently treat as peer-reviewed primary evidence",
            "general_web": "retrieval/support only unless independently reviewed and explicitly justified",
            "institutional_classification": "standard academic/government domains plus narrow verified Extension/publication hosts and explicit institutional attribution",
            "source_age": "review flag only; age alone does not invalidate primary evidence",
            "missing_year": "review metadata gap; do not infer freshness from retrieval date",
            "automatic_training_mutation": False,
        },
        "profiles_without_doi": profiles_without_doi,
        "profiles_general_web_only": profiles_general_web_only,
        "general_web_sources_requiring_review": len(general_web_review),
        "general_web_remediation_queue": general_web_review,
        "missing_publication_year": missing_year,
        "missing_year_remediation_queue": missing_year_review,
        "age_review_threshold_years": AGE_REVIEW_YEARS,
        "sources_requiring_age_scope_review": len(age_review),
        "age_scope_review_queue": age_review,
        "hard_errors": len(hard_errors),
        "errors": hard_errors,
    }


def self_test() -> None:
    profiles = [{
        "id": "p1",
        "reviewStatus": "reviewed",
        "sources": [
            {"doi": "10.1234/Example", "url": "https://doi.org/10.1234/Example", "year": 2025, "supportedClaims": ["a"]},
            {"url": "https://extension.example.edu/guide", "year": 2010, "supportedClaims": ["b"]},
            {"url": "https://Example.com/page/#fragment", "supportedClaims": ["c"]},
        ],
    }]
    report = audit(profiles, current_year=2026)
    assert report["hard_errors"] == 0
    assert report["schema_version"] == "grow-doc-source-evidence-audit-v3"
    assert report["evidence_tiers"] == {
        "general_web": 1,
        "institutional_web": 1,
        "scholarly_doi": 1,
    }
    assert report["sources_requiring_age_scope_review"] == 1
    assert report["general_web_sources_requiring_review"] == 1
    assert report["general_web_remediation_queue"][0]["source_id"] == "url:https://example.com/page"
    assert report["missing_publication_year"] == 1
    assert report["missing_year_remediation_queue"][0]["profile_id"] == "p1"
    assert canonical_source_id({"doi": "https://doi.org/10.1234/Example"}) == "doi:10.1234/example"

    assert evidence_tier({
        "url": "https://pnwhandbooks.org/plantdisease/example",
        "organization": "Pacific Northwest Pest Management Handbooks",
    }) == "institutional_web"
    assert evidence_tier({
        "url": "https://bpb-us-e1.wpmucdn.com/example.pdf",
        "organization": "Cornell University Plant Disease Diagnostic Clinic",
    }) == "institutional_web"
    assert evidence_tier({
        "url": "https://onspecialtycrops.ca/example",
        "publisher": "Ontario Ministry of Agriculture, Food and Rural Affairs",
    }) == "institutional_web"

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