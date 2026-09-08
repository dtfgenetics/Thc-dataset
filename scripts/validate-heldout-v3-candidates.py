#!/usr/bin/env python3
"""Validate Grow Doc heldout-v3 candidate cases without external dependencies."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

PATH = Path("model_tuning/eval/heldout_v3_candidates.jsonl")
REQUIRED = {
    "factuality", "diagnostic", "science", "citation_accuracy",
    "hallucination", "education", "regression", "grounded_qa",
}


def canonical(value: str) -> str:
    value = str(value or "").strip()
    prefix, sep, rest = value.partition(":")
    if not sep:
        return value
    if prefix.lower() == "doi":
        return f"doi:{rest.lower()}"
    return f"{prefix.lower()}:{rest}"


def validate(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    ids = [str(row.get("id", "")).strip() for row in rows]
    duplicates = [key for key, count in Counter(ids).items() if key and count > 1]
    if duplicates:
        errors.append("duplicate ids: " + ", ".join(sorted(duplicates)))
    categories = Counter(str(row.get("category", "")).strip() for row in rows)
    if set(categories) != REQUIRED:
        errors.append(f"candidate categories must be exactly {sorted(REQUIRED)}; got {sorted(categories)}")
    if any(count != 1 for count in categories.values()):
        errors.append("candidate file must contain exactly one new case per required evaluation slice")

    for index, row in enumerate(rows, 1):
        label = row.get("id") or f"row-{index}"
        if row.get("candidate_status") != "reviewed_candidate":
            errors.append(f"{label}: candidate_status must be reviewed_candidate")
        if row.get("promotion_eligible") is not False:
            errors.append(f"{label}: promotion_eligible must remain false until benchmark versioning/review")
        if row.get("difficulty") not in {"medium", "hard"}:
            errors.append(f"{label}: candidate cases must be medium or hard")
        for key in ("prompt", "expected_points", "must_cite", "forbidden_claims", "source_metadata"):
            if not row.get(key):
                errors.append(f"{label}: missing {key}")
        citations = {canonical(value) for value in row.get("must_cite") or [] if canonical(value)}
        source = row.get("source_metadata") or {}
        evidence = set()
        if source.get("doi"):
            evidence.add(canonical(f"doi:{source['doi']}"))
        if source.get("url"):
            evidence.add(canonical(f"url:{source['url']}"))
        if citations and evidence and citations.isdisjoint(evidence):
            errors.append(f"{label}: must_cite does not match source_metadata provenance")
        if not source.get("source_id"):
            errors.append(f"{label}: source_metadata.source_id is required")
        if not (source.get("doi") or source.get("url")):
            errors.append(f"{label}: source_metadata requires DOI or URL")
        if len(row.get("expected_points") or []) < 2:
            errors.append(f"{label}: expected_points needs at least two independently scoreable points")
    return errors


def load(path: Path = PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def self_test() -> None:
    rows = load()
    assert not validate(rows), validate(rows)
    bad = [dict(row) for row in rows]
    bad[0] = dict(bad[0]); bad[0]["promotion_eligible"] = True
    assert any("promotion_eligible" in error for error in validate(bad))
    bad = [dict(row) for row in rows]
    bad[0] = dict(bad[0]); bad[0]["must_cite"] = ["doi:10.0000/not-the-source"]
    assert any("must_cite does not match" in error for error in validate(bad))
    print("heldout-v3 candidate validator self-test: PASS")


if __name__ == "__main__":
    errors = validate(load())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    self_test()
    print(f"heldout-v3 candidates valid: {PATH}")
