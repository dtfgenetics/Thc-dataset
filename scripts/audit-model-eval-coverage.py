#!/usr/bin/env python3
"""Audit Grow Doc held-out evaluation coverage without external dependencies."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

DEFAULT_PATH = Path("model_tuning/eval/heldout_v2.jsonl")
REQUIRED_CATEGORIES = {
    "factuality",
    "diagnostic",
    "science",
    "citation_accuracy",
    "hallucination",
    "education",
    "regression",
    "grounded_qa",
}
CRITICAL_CATEGORIES = {"diagnostic", "citation_accuracy", "hallucination"}


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: each row must be an object")
        rows.append(row)
    return rows


def audit(rows: list[dict]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if len(rows) < 12:
        errors.append(f"held-out benchmark has only {len(rows)} cases; minimum is 12")

    ids = [str(r.get("id", "")).strip() for r in rows]
    missing_ids = sum(not x for x in ids)
    if missing_ids:
        errors.append(f"{missing_ids} cases are missing ids")
    duplicates = sorted(k for k, v in Counter(ids).items() if k and v > 1)
    if duplicates:
        errors.append(f"duplicate case ids: {', '.join(duplicates)}")

    prompts = [str(r.get("prompt", "")).strip() for r in rows]
    duplicate_prompts = sum(v - 1 for k, v in Counter(prompts).items() if k and v > 1)
    if duplicate_prompts:
        errors.append(f"{duplicate_prompts} exact duplicate prompts detected")

    categories = Counter(str(r.get("category", "")).strip() for r in rows)
    missing_categories = sorted(REQUIRED_CATEGORIES - set(categories))
    if missing_categories:
        errors.append(f"missing required categories: {', '.join(missing_categories)}")

    for category in sorted(CRITICAL_CATEGORIES):
        hard = sum(
            1
            for r in rows
            if r.get("category") == category and r.get("difficulty") == "hard"
        )
        if hard < 1:
            warnings.append(f"critical category {category} has no hard case; add one in the next benchmark version")

    for index, row in enumerate(rows, start=1):
        label = row.get("id") or f"row-{index}"
        if not row.get("expected_points"):
            errors.append(f"{label}: missing expected_points")
        if not row.get("must_cite"):
            errors.append(f"{label}: missing must_cite")
        if not row.get("forbidden_claims"):
            errors.append(f"{label}: missing forbidden_claims")
        source = row.get("source_metadata")
        if not isinstance(source, dict):
            errors.append(f"{label}: missing source_metadata")
            continue
        if not source.get("source_id"):
            errors.append(f"{label}: source_metadata.source_id is required")
        if not (source.get("doi") or source.get("url")):
            errors.append(f"{label}: source_metadata requires DOI or URL")

    source_ids = {
        str((r.get("source_metadata") or {}).get("source_id", "")).strip()
        for r in rows
    } - {""}
    if len(source_ids) < 3:
        errors.append(f"benchmark uses only {len(source_ids)} distinct scientific sources; minimum is 3")

    if rows:
        largest_category, largest_count = categories.most_common(1)[0]
        share = largest_count / len(rows)
        if share > 0.50:
            errors.append(
                f"category {largest_category} dominates {share:.1%} of benchmark; maximum is 50%"
            )

    for category in sorted(REQUIRED_CATEGORIES):
        if categories.get(category, 0) == 1:
            warnings.append(f"category {category} has only one case; expand before relying on fine-grained deltas")

    return {
        "cases": len(rows),
        "categories": dict(sorted(categories.items())),
        "distinct_sources": len(source_ids),
        "errors": errors,
        "warnings": warnings,
    }


def run_self_test() -> None:
    good = []
    cats = sorted(REQUIRED_CATEGORIES)
    for i in range(12):
        category = cats[i % len(cats)]
        difficulty = "hard" if category in CRITICAL_CATEGORIES else "medium"
        good.append(
            {
                "id": f"case-{i}",
                "category": category,
                "difficulty": difficulty,
                "prompt": f"prompt {i}",
                "expected_points": ["fact"],
                "must_cite": ["doi:10.0000/test"],
                "forbidden_claims": ["overclaim"],
                "source_metadata": {
                    "source_id": f"source-{i % 3}",
                    "doi": f"10.0000/test{i % 3}",
                },
            }
        )
    result = audit(good)
    if result["errors"]:
        raise SystemExit(f"self-test valid fixture failed: {result['errors']}")

    bad = [dict(r) for r in good]
    bad[1]["id"] = bad[0]["id"]
    bad[2]["prompt"] = bad[0]["prompt"]
    bad = [r for r in bad if r["category"] != "hallucination"]
    result = audit(bad)
    if not result["errors"]:
        raise SystemExit("self-test invalid fixture unexpectedly passed")

    print("model eval coverage self-test: PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=str(DEFAULT_PATH))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    path = Path(args.path)
    result = audit(load_rows(path))
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
