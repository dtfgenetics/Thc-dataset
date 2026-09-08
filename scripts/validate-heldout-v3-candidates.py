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

    source_ids: list[str] = []
    source_evidence: list[str] = []

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

        if not citations:
            errors.append(f"{label}: at least one canonical must_cite source is required")
        if citations and evidence and not citations.issubset(evidence):
            missing = sorted(citations - evidence)
            errors.append(f"{label}: must_cite contains provenance not present in source_metadata: {missing}")

        source_id = str(source.get("source_id", "")).strip()
        if not source_id:
            errors.append(f"{label}: source_metadata.source_id is required")
        else:
            source_ids.append(source_id)
        if not str(source.get("title", "")).strip():
            errors.append(f"{label}: source_metadata.title is required")
        year = source.get("year")
        if not isinstance(year, int) or year < 1900 or year > 2100:
            errors.append(f"{label}: source_metadata.year must be a plausible integer year")
        if not evidence:
            errors.append(f"{label}: source_metadata requires DOI or URL")
        else:
            source_evidence.extend(sorted(evidence))
        if len(row.get("expected_points") or []) < 2:
            errors.append(f"{label}: expected_points needs at least two independently scoreable points")

    duplicate_source_ids = [key for key, count in Counter(source_ids).items() if count > 1]
    if duplicate_source_ids:
        errors.append("candidate source_metadata.source_id values must be unique: " + ", ".join(sorted(duplicate_source_ids)))
    duplicate_evidence = [key for key, count in Counter(source_evidence).items() if count > 1]
    if duplicate_evidence:
        errors.append("candidate source DOI/URL identities must be unique across slices: " + ", ".join(sorted(duplicate_evidence)))

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
    bad[0] = dict(bad[0]); bad[0]["must_cite"] = [rows[0]["must_cite"][0], "doi:10.0000/not-the-source"]
    assert any("must_cite contains provenance" in error for error in validate(bad))

    bad = [dict(row) for row in rows]
    bad[0] = dict(bad[0]); bad[0]["source_metadata"] = dict(bad[0]["source_metadata"]); bad[0]["source_metadata"].pop("title", None)
    assert any("source_metadata.title" in error for error in validate(bad))

    bad = [dict(row) for row in rows]
    bad[1] = dict(bad[1]); bad[1]["source_metadata"] = dict(bad[1]["source_metadata"])
    bad[1]["source_metadata"]["source_id"] = rows[0]["source_metadata"]["source_id"]
    assert any("source_metadata.source_id values must be unique" in error for error in validate(bad))

    bad = [dict(row) for row in rows]
    bad[1] = dict(bad[1]); bad[1]["source_metadata"] = dict(bad[1]["source_metadata"])
    bad[1]["source_metadata"]["doi"] = rows[0]["source_metadata"]["doi"]
    bad[1]["must_cite"] = list(rows[0]["must_cite"])
    assert any("source DOI/URL identities must be unique" in error for error in validate(bad))

    print("heldout-v3 candidate validator self-test: PASS")


if __name__ == "__main__":
    errors = validate(load())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    self_test()
    print(f"heldout-v3 candidates valid: {PATH}")
