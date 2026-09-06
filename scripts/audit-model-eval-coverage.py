#!/usr/bin/env python3
"""Audit Grow Doc held-out evaluation coverage without external dependencies."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
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
MIN_PROMOTION_CASES_PER_CATEGORY = 2
MIN_PROMOTION_EVIDENCE_SOURCES_PER_CATEGORY = 2


def canonical_source_id(value: str) -> str:
    source_id = str(value or "").strip()
    if not source_id:
        return ""
    prefix, sep, rest = source_id.partition(":")
    if not sep:
        return source_id
    prefix_l = prefix.lower()
    rest = rest.strip()
    if prefix_l == "doi":
        return f"doi:{rest.lower()}"
    if prefix_l in {"url", "source"}:
        return f"{prefix_l}:{rest}"
    return source_id


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


def audit(rows: list[dict], *, require_replicated_slices: bool = False) -> dict:
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

    evidence_sources_by_category: dict[str, set[str]] = defaultdict(set)
    for index, row in enumerate(rows, start=1):
        label = row.get("id") or f"row-{index}"
        if not row.get("expected_points"):
            errors.append(f"{label}: missing expected_points")
        if not row.get("must_cite"):
            errors.append(f"{label}: missing must_cite")
        if not row.get("forbidden_claims"):
            errors.append(f"{label}: missing forbidden_claims")
        category = str(row.get("category", "")).strip()
        for cite in row.get("must_cite") or []:
            canonical = canonical_source_id(str(cite))
            if canonical:
                evidence_sources_by_category[category].add(canonical)
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
        case_count = categories.get(category, 0)
        evidence_count = len(evidence_sources_by_category.get(category, set()))
        if require_replicated_slices:
            if case_count < MIN_PROMOTION_CASES_PER_CATEGORY:
                errors.append(
                    f"promotion category {category} has only {case_count} case(s); "
                    f"minimum is {MIN_PROMOTION_CASES_PER_CATEGORY}"
                )
            if evidence_count < MIN_PROMOTION_EVIDENCE_SOURCES_PER_CATEGORY:
                errors.append(
                    f"promotion category {category} uses only {evidence_count} distinct required evidence source(s); "
                    f"minimum is {MIN_PROMOTION_EVIDENCE_SOURCES_PER_CATEGORY}"
                )
        elif case_count == 1:
            warnings.append(f"category {category} has only one case; expand before relying on fine-grained deltas")

    return {
        "cases": len(rows),
        "categories": dict(sorted(categories.items())),
        "distinct_sources": len(source_ids),
        "required_evidence_sources_by_category": {
            category: len(evidence_sources_by_category.get(category, set()))
            for category in sorted(REQUIRED_CATEGORIES)
        },
        "replicated_slice_contract": require_replicated_slices,
        "errors": errors,
        "warnings": warnings,
    }


def _fixture(*, replicated: bool) -> list[dict]:
    cats = sorted(REQUIRED_CATEGORIES)
    repeats = 2 if replicated else 1
    rows: list[dict] = []
    for repeat in range(repeats):
        for i, category in enumerate(cats):
            difficulty = "hard" if category in CRITICAL_CATEGORIES else "medium"
            source_index = repeat
            rows.append(
                {
                    "id": f"case-{repeat}-{i}",
                    "category": category,
                    "difficulty": difficulty,
                    "prompt": f"prompt {repeat} {i}",
                    "expected_points": ["fact"],
                    "must_cite": [f"doi:10.0000/{category}-{source_index}"],
                    "forbidden_claims": ["overclaim"],
                    "source_metadata": {
                        "source_id": f"source-{category}-{source_index}",
                        "doi": f"10.0000/{category}-{source_index}",
                    },
                }
            )
    return rows


def run_self_test() -> None:
    good = _fixture(replicated=True)
    result = audit(good, require_replicated_slices=True)
    if result["errors"]:
        raise SystemExit(f"self-test valid promotion fixture failed: {result['errors']}")

    bad = _fixture(replicated=True)
    bad = [r for r in bad if not (r["category"] == "hallucination" and r["id"].startswith("case-1-"))]
    result = audit(bad, require_replicated_slices=True)
    if not any("promotion category hallucination has only 1 case" in error for error in result["errors"]):
        raise SystemExit("self-test did not reject a single-case protected slice")

    bad_source = _fixture(replicated=True)
    for row in bad_source:
        if row["category"] == "citation_accuracy":
            row["must_cite"] = ["doi:10.0000/shared-citation-source"]
    result = audit(bad_source, require_replicated_slices=True)
    if not any("promotion category citation_accuracy uses only 1 distinct required evidence source" in error for error in result["errors"]):
        raise SystemExit("self-test did not reject a single-source protected slice")

    legacy = _fixture(replicated=False)
    while len(legacy) < 12:
        i = len(legacy)
        row = dict(legacy[i % len(legacy)])
        row["id"] = f"legacy-extra-{i}"
        row["prompt"] = f"legacy prompt {i}"
        legacy.append(row)
    result = audit(legacy, require_replicated_slices=False)
    if result["errors"]:
        raise SystemExit(f"self-test legacy warning fixture failed: {result['errors']}")
    if not result["warnings"]:
        raise SystemExit("self-test legacy fixture should retain single-case warnings")

    print("model eval coverage self-test: PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=str(DEFAULT_PATH))
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--require-replicated-slices",
        action="store_true",
        help="Fail closed unless every protected promotion slice has at least two cases and two distinct required evidence sources.",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    path = Path(args.path)
    result = audit(load_rows(path), require_replicated_slices=args.require_replicated_slices)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
