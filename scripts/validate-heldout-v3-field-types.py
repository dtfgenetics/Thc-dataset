#!/usr/bin/env python3
"""Fail closed on malformed structured fields in heldout-v3 candidates.

This complements validate-heldout-v3-candidates.py by ensuring fields that are
conceptually lists cannot pass validation as truthy scalars or objects.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from urllib.parse import urlparse

PATH = Path("model_tuning/eval/heldout_v3_candidates.jsonl")


def load(path: Path = PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def nonempty_string_list(value: object, *, min_items: int = 1) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= min_items
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def valid_citation(value: str) -> bool:
    value = value.strip()
    if value.lower().startswith("doi:"):
        return bool(value[4:].strip()) and "/" in value[4:]
    if value.lower().startswith("url:"):
        parsed = urlparse(value[4:].strip())
        return parsed.scheme == "https" and bool(parsed.netloc)
    return False


def validate(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    for index, row in enumerate(rows, 1):
        label = str(row.get("id") or f"row-{index}")
        prompt = row.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"{label}: prompt must be a non-empty string")

        expected = row.get("expected_points")
        if not nonempty_string_list(expected, min_items=2):
            errors.append(f"{label}: expected_points must be a list of at least two non-empty strings")

        forbidden = row.get("forbidden_claims")
        if not nonempty_string_list(forbidden):
            errors.append(f"{label}: forbidden_claims must be a non-empty list of non-empty strings")

        citations = row.get("must_cite")
        if not nonempty_string_list(citations):
            errors.append(f"{label}: must_cite must be a non-empty list of non-empty strings")
        elif not all(valid_citation(item) for item in citations):
            errors.append(f"{label}: every must_cite entry must be canonical doi:... or https url:...")

        source = row.get("source_metadata")
        if not isinstance(source, dict):
            errors.append(f"{label}: source_metadata must be an object")
            continue
        for key in ("source_id", "title"):
            value = source.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}: source_metadata.{key} must be a non-empty string")
        year = source.get("year")
        if isinstance(year, bool) or not isinstance(year, int) or year < 1900 or year > 2100:
            errors.append(f"{label}: source_metadata.year must be a plausible integer")

        if row.get("promotion_eligible") is not False:
            errors.append(f"{label}: promotion_eligible must remain false")
    return errors


def self_test(rows: list[dict]) -> None:
    assert rows, "candidate dataset must not be empty"
    assert not validate(rows), validate(rows)

    mutations = []
    bad = copy.deepcopy(rows); bad[0]["expected_points"] = "truthy-but-not-a-list"; mutations.append(bad)
    bad = copy.deepcopy(rows); bad[0]["forbidden_claims"] = {"bad": "shape"}; mutations.append(bad)
    bad = copy.deepcopy(rows); bad[0]["must_cite"] = [""]; mutations.append(bad)
    bad = copy.deepcopy(rows); bad[0]["must_cite"] = ["doi:not-a-doi"]; mutations.append(bad)
    bad = copy.deepcopy(rows); bad[0]["source_metadata"] = "truthy-but-not-an-object"; mutations.append(bad)
    bad = copy.deepcopy(rows); bad[0]["promotion_eligible"] = True; mutations.append(bad)
    for mutation in mutations:
        assert validate(mutation), "malformed mutation unexpectedly passed"
    print("heldout-v3 field-type validator self-test: PASS")


def main() -> int:
    rows = load()
    errors = validate(rows)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    self_test(rows)
    print(f"heldout-v3 structured fields valid: {PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
