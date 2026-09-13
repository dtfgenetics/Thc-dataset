#!/usr/bin/env python3
"""Validate reviewed source-metadata findings without changing training eligibility."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "model_tuning/evidence/source_metadata_reviews_v1.jsonl"
ALLOWED_STATUS = {"verified-current", "verified-unresolved", "rejected-metadata"}
ALLOWED_SCOPE = {"publisher-page-metadata", "doi-metadata", "institutional-catalog-metadata"}


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            row = json.loads(raw)
            row["_line"] = line_no
            rows.append(row)
    return rows


def validate(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for row in rows:
        line = row["_line"]
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id.startswith(("url:", "doi:")):
            errors.append(f"line {line}: invalid canonical source_id")
            continue
        if source_id in seen:
            errors.append(f"line {line}: duplicate source_id {source_id}")
        seen.add(source_id)
        if row.get("review_status") not in ALLOWED_STATUS:
            errors.append(f"line {line}: invalid review_status")
        if row.get("evidence_scope") not in ALLOWED_SCOPE:
            errors.append(f"line {line}: invalid evidence_scope")
        try:
            dt.date.fromisoformat(str(row.get("checked_date")))
        except ValueError:
            errors.append(f"line {line}: checked_date must be YYYY-MM-DD")
        if row.get("changes_training_eligibility") is not False:
            errors.append(f"line {line}: metadata review must not change training eligibility")
        if row.get("rag_first") is not True:
            errors.append(f"line {line}: rag_first must remain true")
        year = row.get("year")
        publication_date = row.get("publication_date")
        if row.get("review_status") == "verified-unresolved":
            if year is not None or publication_date is not None:
                errors.append(f"line {line}: unresolved metadata must not invent a year/date")
        elif year is not None:
            if not isinstance(year, int) or year < 1900 or year > 2100:
                errors.append(f"line {line}: invalid year")
            if not isinstance(publication_date, str) or not publication_date.startswith(str(year)):
                errors.append(f"line {line}: publication_date must agree with year")
        if not isinstance(row.get("finding"), str) or len(row["finding"].strip()) < 20:
            errors.append(f"line {line}: finding is missing or too short")
    return errors


def self_test() -> None:
    good = [{
        "_line": 1,
        "source_id": "url:https://example.test/source",
        "checked_date": "2026-09-13",
        "review_status": "verified-unresolved",
        "publication_date": None,
        "year": None,
        "finding": "Publisher page exposes no publication date.",
        "evidence_scope": "publisher-page-metadata",
        "changes_training_eligibility": False,
        "rag_first": True,
    }]
    assert validate(good) == []
    bad = [dict(good[0], _line=2, year=2024)]
    assert any("must not invent" in error for error in validate(bad))
    print("source metadata review self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    rows = load_rows(args.input)
    errors = validate(rows)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row["review_status"]] = statuses.get(row["review_status"], 0) + 1
    print(json.dumps({"records": len(rows), "statuses": statuses, "training_eligibility_changed": False}, sort_keys=True))
    print("source metadata reviews: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
