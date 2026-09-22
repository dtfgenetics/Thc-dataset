#!/usr/bin/env python3
"""Report missing replicated cases/evidence sources for Grow Doc held-out promotion."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

PATH = Path("model_tuning/eval/heldout_v3_candidates.jsonl")
REQUIRED = (
    "factuality", "diagnostic", "science", "citation_accuracy",
    "hallucination", "education", "regression", "grounded_qa",
)
MIN_CASES = 2
MIN_SOURCES = 2


def canonical(value: str) -> str:
    value = str(value or "").strip()
    prefix, sep, rest = value.partition(":")
    if sep and prefix.lower() == "doi":
        return f"doi:{rest.strip().lower()}"
    return value


def report(rows: list[dict]) -> dict:
    cases = Counter(str(row.get("category", "")).strip() for row in rows)
    sources: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        category = str(row.get("category", "")).strip()
        for citation in row.get("must_cite") or []:
            identity = canonical(citation)
            if identity:
                sources[category].add(identity)

    gaps = {}
    for category in REQUIRED:
        case_count = cases.get(category, 0)
        source_count = len(sources.get(category, set()))
        gaps[category] = {
            "cases": case_count,
            "distinct_required_sources": source_count,
            "additional_cases_needed": max(0, MIN_CASES - case_count),
            "additional_distinct_sources_needed": max(0, MIN_SOURCES - source_count),
            "promotion_ready": case_count >= MIN_CASES and source_count >= MIN_SOURCES,
        }
    return {
        "minimum_cases_per_slice": MIN_CASES,
        "minimum_distinct_sources_per_slice": MIN_SOURCES,
        "promotion_ready": all(item["promotion_ready"] for item in gaps.values()),
        "gaps": gaps,
    }


def load(path: Path = PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def self_test() -> None:
    rows = []
    for category in REQUIRED:
        for i in range(2):
            rows.append({"category": category, "must_cite": [f"doi:10.0000/{category}-{i}"]})
    result = report(rows)
    assert result["promotion_ready"] is True
    rows.pop()
    result = report(rows)
    assert result["promotion_ready"] is False
    assert result["gaps"]["grounded_qa"]["additional_cases_needed"] == 1
    assert result["gaps"]["grounded_qa"]["additional_distinct_sources_needed"] == 1
    print("heldout promotion gap reporter self-test: PASS")


if __name__ == "__main__":
    self_test()
    print(json.dumps(report(load()), indent=2, sort_keys=True))
