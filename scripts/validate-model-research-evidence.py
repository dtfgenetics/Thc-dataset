#!/usr/bin/env python3
"""Validate standalone Grow Doc open-weight model research evidence records.

These records are discovery/evidence artifacts only. They must remain fail-closed for
benchmarking, training, adapter combination, and promotion until immutable runtime
and held-out contracts are established elsewhere.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

SCHEMA = "grow-doc-base-model-research-v1"
REQUIRED_POLICY_TRUE = {
    "rag_first_for_factual_knowledge",
    "upstream_benchmark_claims_are_not_grow_doc_evidence",
    "no_training_or_promotion_without_heldout_improvement",
    "no_adapter_or_model_soup_combination_without_measured_gain",
}
ELIGIBILITY_FIELDS = {
    "benchmark_eligible",
    "training_eligible",
    "adapter_combination_eligible",
}


def valid_https(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot parse {path}: {exc}"]

    if data.get("schema_version") != SCHEMA:
        errors.append(f"schema_version must equal {SCHEMA}")

    candidate = data.get("candidate")
    if not isinstance(candidate, dict):
        return errors + ["candidate must be an object"]

    cid = candidate.get("id")
    if not isinstance(cid, str) or not cid.strip():
        errors.append("candidate.id must be non-empty")

    repo_id = candidate.get("repo_id")
    if not isinstance(repo_id, str) or not re.fullmatch(r"[^/\s]+/[^/\s]+", repo_id):
        errors.append("candidate.repo_id must be owner/name")

    checked = candidate.get("evidence_checked_at")
    try:
        date.fromisoformat(checked)
    except Exception:
        errors.append("candidate.evidence_checked_at must be ISO YYYY-MM-DD")

    if not isinstance(candidate.get("license"), str) or not candidate.get("license", "").strip():
        errors.append("candidate.license must be non-empty")
    if not valid_https(candidate.get("license_source")):
        errors.append("candidate.license_source must be https")
    if not valid_https(candidate.get("official_announcement")):
        errors.append("candidate.official_announcement must be https")

    architecture = candidate.get("architecture")
    if not isinstance(architecture, dict):
        errors.append("candidate.architecture must be an object")
    else:
        for field in ("family", "parameters_total_billion", "context_length_tokens"):
            if field not in architecture:
                errors.append(f"candidate.architecture.{field} is required")

    assessment = candidate.get("grow_doc_assessment")
    if not isinstance(assessment, dict):
        return errors + ["candidate.grow_doc_assessment must be an object"]

    for field in ELIGIBILITY_FIELDS:
        value = assessment.get(field)
        if not isinstance(value, bool):
            errors.append(f"candidate.grow_doc_assessment.{field} must be boolean")
        elif value:
            errors.append(
                f"candidate.grow_doc_assessment.{field} must remain false in standalone research evidence"
            )

    blockers = assessment.get("blocking_requirements")
    if not isinstance(blockers, list) or not blockers or not all(isinstance(x, str) and x.strip() for x in blockers):
        errors.append("candidate.grow_doc_assessment.blocking_requirements must be a non-empty string list")

    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")
    else:
        seen_urls: set[str] = set()
        for idx, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"evidence[{idx}] must be an object")
                continue
            url = item.get("url")
            if not valid_https(url):
                errors.append(f"evidence[{idx}].url must be https")
            elif url in seen_urls:
                errors.append(f"duplicate evidence url: {url}")
            else:
                seen_urls.add(url)
            supports = item.get("supports")
            if not isinstance(supports, list) or not supports or not all(isinstance(x, str) and x.strip() for x in supports):
                errors.append(f"evidence[{idx}].supports must be a non-empty string list")

    policy = data.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        for field in sorted(REQUIRED_POLICY_TRUE):
            if policy.get(field) is not True:
                errors.append(f"policy.{field} must be true")

    return errors


def discover() -> list[Path]:
    return sorted(
        p
        for p in Path("model_tuning/config").glob("*_research_*.json")
        if not p.name.startswith("base_model_research_")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    paths = [Path(p) for p in args.paths] if args.paths else discover()
    if not paths:
        print("No standalone model research evidence files found.")
        return 0

    failures = 0
    for path in paths:
        errors = validate(path)
        if errors:
            failures += 1
            print(f"{path}: FAILED")
            for error in errors:
                print(f"- {error}")
        else:
            print(f"{path}: passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
