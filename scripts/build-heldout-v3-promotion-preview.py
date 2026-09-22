#!/usr/bin/env python3
"""Build and validate a non-promoting 16-case Heldout-v3 preview.

This script never mutates the protected candidate benchmark. It combines the reviewed
13-case pool with the separately reviewed final-replication pool, then fails closed
unless every protected slice has exactly two cases backed by two distinct sources.
The output remains candidate-only; promotion requires a separate reviewed change.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "model_tuning/eval/heldout_v3_candidates.jsonl"
FINAL = ROOT / "model_tuning/eval/candidates/heldout_v3_final_replication_v1.jsonl"
REVIEW = ROOT / "model_tuning/eval/candidates/heldout_v3_final_replication_v1.review.json"
REQUIRED = {
    "factuality", "diagnostic", "science", "citation_accuracy",
    "hallucination", "education", "regression", "grounded_qa",
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def source_identity(row: dict) -> str:
    meta = row.get("source_metadata") or {}
    return (meta.get("doi") or meta.get("url") or meta.get("source_id") or "").strip().lower()


def validate(rows: list[dict], final_rows: list[dict], reviews: dict) -> None:
    ids = [r.get("id") for r in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate candidate id in promotion preview")
    if len(rows) != 16:
        raise SystemExit(f"expected 16 preview cases, found {len(rows)}")

    counts = Counter(r.get("category") for r in rows)
    if set(counts) != REQUIRED:
        raise SystemExit(f"category mismatch: {sorted(counts)}")
    bad_counts = {k: v for k, v in counts.items() if v != 2}
    if bad_counts:
        raise SystemExit(f"each protected slice must have exactly two cases: {bad_counts}")

    by_category: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.get("candidate_status") != "reviewed_candidate":
            raise SystemExit(f"{row.get('id')}: not a reviewed candidate")
        if row.get("promotion_eligible") is not False:
            raise SystemExit(f"{row.get('id')}: preview must remain promotion_eligible=false")
        ident = source_identity(row)
        if not ident:
            raise SystemExit(f"{row.get('id')}: missing source identity")
        by_category[row["category"]].add(ident)
        must_cite = row.get("must_cite") or []
        doi = (row.get("source_metadata") or {}).get("doi")
        if doi and f"doi:{doi}" not in must_cite:
            raise SystemExit(f"{row.get('id')}: DOI metadata is not preserved in must_cite")

    weak = {k: len(v) for k, v in by_category.items() if len(v) != 2}
    if weak:
        raise SystemExit(f"each slice needs two distinct required sources: {weak}")

    reviewed = {r.get("candidate_id") for r in reviews.get("reviews", []) if r.get("source_identity_verified") is True and r.get("claim_scope_review") == "pass"}
    final_ids = {r["id"] for r in final_rows}
    missing = sorted(final_ids - reviewed)
    if missing:
        raise SystemExit(f"final replication cases missing passing source review: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Optional path for deterministic preview JSONL")
    args = parser.parse_args()

    base = load_jsonl(BASE)
    final = load_jsonl(FINAL)
    reviews = json.loads(REVIEW.read_text(encoding="utf-8"))
    rows = base + final
    validate(rows, final, reviews)

    rendered = "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print("Heldout-v3 promotion preview: PASS")
    print("cases=16 slices=8 cases_per_slice=2 distinct_sources_per_slice=2")
    print("status=candidate_only_not_promotion_eligible")


if __name__ == "__main__":
    main()
