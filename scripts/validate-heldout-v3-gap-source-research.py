#!/usr/bin/env python3
"""Validate independently researched sources for remaining heldout-v3 slice gaps."""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("model_tuning/eval/candidates/heldout_v3_gap_source_research_v1.json")
EXPECTED_SLICES = {"hallucination", "education", "regression"}


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "grow-doc-heldout-v3-gap-source-research-v1":
        errors.append("unsupported schema_version")
    if data.get("promotion_eligible") is not False:
        errors.append("research artifact must not promote benchmark cases")
    if data.get("rag_first") is not True:
        errors.append("rag_first must remain true")
    targets = set(data.get("target_slices") or [])
    if targets != EXPECTED_SLICES:
        errors.append(f"target_slices must be exactly {sorted(EXPECTED_SLICES)}")
    rows = data.get("sources") or []
    if len(rows) != len(EXPECTED_SLICES):
        errors.append("exactly one independently sourced research record is required per remaining slice")
    seen_slices: set[str] = set()
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()
    for row in rows:
        label = str(row.get("source_id", "")).strip() or "unnamed"
        category = str(row.get("target_slice", "")).strip()
        if category not in EXPECTED_SLICES:
            errors.append(f"{label}: unexpected target_slice")
        if category in seen_slices:
            errors.append(f"{label}: duplicate target_slice {category}")
        seen_slices.add(category)
        if label == "unnamed" or label in seen_ids:
            errors.append(f"{label}: source_id must be unique and non-empty")
        seen_ids.add(label)
        doi = str(row.get("doi", "")).strip().lower()
        if not doi.startswith("10.") or doi in seen_dois:
            errors.append(f"{label}: DOI must be unique and canonical")
        seen_dois.add(doi)
        if row.get("source_identity_verified") is not True:
            errors.append(f"{label}: source_identity_verified must be true")
        if row.get("claim_scope_review") != "pass":
            errors.append(f"{label}: claim_scope_review must be pass")
        url = str(row.get("publisher_url", "")).strip()
        if not url.startswith("https://"):
            errors.append(f"{label}: publisher_url must use https")
        year = row.get("year")
        if isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 2100:
            errors.append(f"{label}: year must be a plausible integer")
        for field in ("title", "candidate_direction", "evidence_notes"):
            if not str(row.get(field, "")).strip():
                errors.append(f"{label}: {field} is required")
    if seen_slices != EXPECTED_SLICES:
        errors.append("source records must cover every target slice exactly once")
    return errors


def self_test() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    assert not validate(data), validate(data)
    bad = json.loads(json.dumps(data)); bad["promotion_eligible"] = True
    assert any("must not promote" in e for e in validate(bad))
    bad = json.loads(json.dumps(data)); bad["sources"][1]["doi"] = bad["sources"][0]["doi"]
    assert any("DOI must be unique" in e for e in validate(bad))
    bad = json.loads(json.dumps(data)); bad["sources"][0]["claim_scope_review"] = "needs_review"
    assert any("claim_scope_review" in e for e in validate(bad))
    print("heldout-v3 gap source research validator self-test: PASS")


if __name__ == "__main__":
    data = json.loads(PATH.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    self_test()
    print(f"heldout-v3 gap source research valid: {PATH}")
