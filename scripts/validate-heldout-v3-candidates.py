#!/usr/bin/env python3
"""Validate Grow Doc heldout-v3 candidate cases without external dependencies."""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

PATH = Path("model_tuning/eval/heldout_v3_candidates.jsonl")
REVIEW_PATH = Path("model_tuning/eval/candidates/heldout_v3_source_review.json")
REQUIRED = {
    "factuality", "diagnostic", "science", "citation_accuracy",
    "hallucination", "education", "regression", "grounded_qa",
}
REQUIRED_REVIEW_POLICY = {
    "source DOI or publisher identity resolves to the cited work",
    "candidate expected_points stay within the cited experiment's reported scope",
    "universal cultivation prescriptions are not inferred from experiment-specific findings",
    "review does not itself promote the candidate benchmark",
}


def canonical(value: str) -> str:
    value = str(value or "").strip()
    prefix, sep, rest = value.partition(":")
    if not sep:
        return value
    if prefix.lower() == "doi":
        return f"doi:{rest.lower()}"
    return f"{prefix.lower()}:{rest}"


def validate_review_ledger(rows: list[dict], ledger: dict) -> list[str]:
    errors: list[str] = []
    if ledger.get("schema_version") != "grow-doc-heldout-v3-source-review-v1":
        errors.append("unsupported or missing heldout-v3 source review schema")
        return errors

    reviewed_at = str(ledger.get("reviewed_at", "")).strip()
    try:
        date.fromisoformat(reviewed_at)
    except ValueError:
        errors.append("source review ledger reviewed_at must be an ISO YYYY-MM-DD date")

    policy = ledger.get("policy") or {}
    if policy.get("promotion_eligible") is not False:
        errors.append("source review ledger must not promote heldout-v3 candidates")
    if policy.get("rag_first") is not True:
        errors.append("source review ledger policy.rag_first must remain true")
    if not str(policy.get("purpose", "")).strip():
        errors.append("source review ledger policy.purpose is required")
    requirements = {str(value).strip() for value in policy.get("requirements") or [] if str(value).strip()}
    missing_requirements = sorted(REQUIRED_REVIEW_POLICY - requirements)
    if missing_requirements:
        errors.append(
            "source review ledger is missing required review-policy statements: "
            + "; ".join(missing_requirements)
        )

    reviews = ledger.get("reviews") or []
    by_candidate = {str(item.get("candidate_id", "")).strip(): item for item in reviews}
    if len(by_candidate) != len(reviews):
        errors.append("source review ledger candidate_id values must be unique and non-empty")

    expected_ids = {str(row.get("id", "")).strip() for row in rows}
    if set(by_candidate) != expected_ids:
        errors.append(
            "source review ledger candidate ids must exactly match heldout-v3 candidates; "
            f"expected {sorted(expected_ids)}, got {sorted(by_candidate)}"
        )
        return errors

    for row in rows:
        label = str(row.get("id", "")).strip()
        review = by_candidate[label]
        source = row.get("source_metadata") or {}
        row_citations = {canonical(value) for value in row.get("must_cite") or [] if canonical(value)}
        review_citation = canonical(review.get("citation", ""))
        if str(review.get("source_id", "")).strip() != str(source.get("source_id", "")).strip():
            errors.append(f"{label}: source review source_id does not match candidate source_metadata")
        if not review_citation or review_citation not in row_citations:
            errors.append(f"{label}: source review citation does not match candidate must_cite")
        if review.get("source_identity_verified") is not True:
            errors.append(f"{label}: source_identity_verified must be true")
        if review.get("claim_scope_review") != "pass":
            errors.append(f"{label}: claim_scope_review must be pass")
        publisher_url = str(review.get("publisher_url", "")).strip()
        if not publisher_url:
            errors.append(f"{label}: publisher_url is required in source review ledger")
        elif not publisher_url.startswith("https://"):
            errors.append(f"{label}: publisher_url must use https")
        if not str(review.get("notes", "")).strip():
            errors.append(f"{label}: source review notes are required")
    return errors


def validate(rows: list[dict], ledger: dict | None = None) -> list[str]:
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

    if ledger is not None:
        errors.extend(validate_review_ledger(rows, ledger))
    return errors


def load(path: Path = PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_review(path: Path = REVIEW_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def self_test() -> None:
    rows = load()
    ledger = load_review()
    assert not validate(rows, ledger), validate(rows, ledger)

    bad = [dict(row) for row in rows]
    bad[0] = dict(bad[0]); bad[0]["promotion_eligible"] = True
    assert any("promotion_eligible" in error for error in validate(bad, ledger))

    bad = [dict(row) for row in rows]
    bad[0] = dict(bad[0]); bad[0]["must_cite"] = [rows[0]["must_cite"][0], "doi:10.0000/not-the-source"]
    assert any("must_cite contains provenance" in error for error in validate(bad, ledger))

    bad = [dict(row) for row in rows]
    bad[0] = dict(bad[0]); bad[0]["source_metadata"] = dict(bad[0]["source_metadata"]); bad[0]["source_metadata"].pop("title", None)
    assert any("source_metadata.title" in error for error in validate(bad, ledger))

    bad = [dict(row) for row in rows]
    bad[1] = dict(bad[1]); bad[1]["source_metadata"] = dict(bad[1]["source_metadata"])
    bad[1]["source_metadata"]["source_id"] = rows[0]["source_metadata"]["source_id"]
    assert any("source_metadata.source_id values must be unique" in error for error in validate(bad, ledger))

    bad = [dict(row) for row in rows]
    bad[1] = dict(bad[1]); bad[1]["source_metadata"] = dict(bad[1]["source_metadata"])
    bad[1]["source_metadata"]["doi"] = rows[0]["source_metadata"]["doi"]
    bad[1]["must_cite"] = list(rows[0]["must_cite"])
    assert any("source DOI/URL identities must be unique" in error for error in validate(bad, ledger))

    broken_ledger = json.loads(json.dumps(ledger))
    broken_ledger["reviews"][0]["citation"] = "doi:10.0000/not-the-source"
    assert any("source review citation" in error for error in validate(rows, broken_ledger))

    broken_ledger = json.loads(json.dumps(ledger))
    broken_ledger["reviews"][0]["claim_scope_review"] = "needs_review"
    assert any("claim_scope_review" in error for error in validate(rows, broken_ledger))

    broken_ledger = json.loads(json.dumps(ledger))
    broken_ledger["reviewed_at"] = "09/11/2026"
    assert any("reviewed_at" in error for error in validate(rows, broken_ledger))

    broken_ledger = json.loads(json.dumps(ledger))
    broken_ledger["policy"]["rag_first"] = False
    assert any("rag_first" in error for error in validate(rows, broken_ledger))

    broken_ledger = json.loads(json.dumps(ledger))
    broken_ledger["policy"]["requirements"] = []
    assert any("required review-policy statements" in error for error in validate(rows, broken_ledger))

    broken_ledger = json.loads(json.dumps(ledger))
    broken_ledger["reviews"][0]["publisher_url"] = "http://example.com/not-secure"
    assert any("publisher_url must use https" in error for error in validate(rows, broken_ledger))

    print("heldout-v3 candidate validator self-test: PASS")


if __name__ == "__main__":
    rows = load()
    ledger = load_review()
    errors = validate(rows, ledger)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    self_test()
    print(f"heldout-v3 candidates valid with reviewed source ledger: {PATH}")
