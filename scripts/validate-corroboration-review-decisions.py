#!/usr/bin/env python3
"""Validate source-verified corroboration review decisions without promoting them.

Review decisions are curation metadata only. They must reference a current priority-review
candidate, preserve distinct canonical source identities, and remain explicitly ineligible for
training and corroboration until a separate human promotion step exists.
"""
from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_DECISIONS = ROOT / "model_tuning/reviews/corroboration_decisions_v1.jsonl"
DEFAULT_PRIORITY = ROOT / "model_tuning/generated/corroboration/discovery_priority_v1.jsonl"
ALLOWED_DECISIONS = {"supported_core_equivalence", "related_but_distinct", "reject"}


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def candidate_key(row: dict) -> tuple[str, frozenset[str]]:
    return (
        row.get("profile_id") or "",
        frozenset({
            row.get("source_a_id") or row.get("source_a", {}).get("canonical_source_id") or "",
            row.get("source_b_id") or row.get("source_b", {}).get("canonical_source_id") or "",
        }),
    )


def validate(decisions: list[dict], priority: list[dict]) -> dict:
    priority_keys = {candidate_key(row) for row in priority}
    seen = set()
    counts = {decision: 0 for decision in sorted(ALLOWED_DECISIONS)}

    for idx, row in enumerate(decisions, 1):
        decision = row.get("decision")
        assert decision in ALLOWED_DECISIONS, f"row {idx}: unsupported decision {decision!r}"
        assert row.get("eligible_for_corroboration") is False, f"row {idx}: corroboration must remain blocked"
        assert row.get("eligible_for_training") is False, f"row {idx}: training must remain blocked"
        assert row.get("promotion_status") == "blocked_pending_human_review", f"row {idx}: invalid promotion status"
        assert row.get("review_method") == "source_verified_model_review", f"row {idx}: review method must be explicit"
        assert row.get("sources_verified") is True, f"row {idx}: sources must be explicitly verified"
        assert row.get("review_date"), f"row {idx}: review_date required"
        source_a = row.get("source_a_id") or ""
        source_b = row.get("source_b_id") or ""
        assert source_a and source_b and source_a != source_b, f"row {idx}: two distinct canonical sources required"
        key = candidate_key(row)
        assert key in priority_keys, f"row {idx}: decision no longer maps to a current priority candidate"
        dedupe_key = (key, row.get("canonical_proposition") or "", decision)
        assert dedupe_key not in seen, f"row {idx}: duplicate decision"
        seen.add(dedupe_key)
        if decision == "supported_core_equivalence":
            assert row.get("canonical_proposition"), f"row {idx}: canonical proposition required"
        assert row.get("notes"), f"row {idx}: review notes required"
        counts[decision] += 1

    return {
        "decisions": len(decisions),
        "supported_core_equivalence": counts["supported_core_equivalence"],
        "related_but_distinct": counts["related_but_distinct"],
        "reject": counts["reject"],
        "training_promoted": 0,
        "corroboration_promoted": 0,
    }


def self_test() -> None:
    priority = [{
        "profile_id": "example",
        "source_a": {"canonical_source_id": "doi:10.1/a"},
        "source_b": {"canonical_source_id": "doi:10.1/b"},
    }]
    decisions = [{
        "profile_id": "example",
        "source_a_id": "doi:10.1/a",
        "source_b_id": "doi:10.1/b",
        "decision": "supported_core_equivalence",
        "canonical_proposition": "A bounded core proposition.",
        "notes": "Verified from both source records.",
        "review_date": "2026-09-10",
        "review_method": "source_verified_model_review",
        "sources_verified": True,
        "promotion_status": "blocked_pending_human_review",
        "eligible_for_corroboration": False,
        "eligible_for_training": False,
    }]
    summary = validate(decisions, priority)
    assert summary["decisions"] == 1
    assert summary["training_promoted"] == 0
    print("Corroboration review decision validator self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=pathlib.Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--priority", type=pathlib.Path, default=DEFAULT_PRIORITY)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    summary = validate(load_jsonl(args.decisions), load_jsonl(args.priority))
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
