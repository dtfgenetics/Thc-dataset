#!/usr/bin/env python3
"""Require claim-level citation bindings for held-out evaluation candidates."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise ValueError(message)


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            fail(f"{path}:{line_no}: invalid JSON: {exc}")
    return rows


def validate_record(record: dict) -> None:
    record_id = str(record.get("id") or "<missing>")
    expected_points = record.get("expected_points")
    must_cite = record.get("must_cite")
    bindings = record.get("claim_source_bindings")
    if not isinstance(expected_points, list) or not expected_points:
        fail(f"{record_id}: expected_points must be a non-empty list")
    if not isinstance(must_cite, list) or not must_cite:
        fail(f"{record_id}: must_cite must be a non-empty list")
    if not isinstance(bindings, list) or len(bindings) != len(expected_points):
        fail(f"{record_id}: claim_source_bindings must contain exactly one binding per expected point")

    expected_indexes = set(range(len(expected_points)))
    seen_indexes: set[int] = set()
    allowed = set(str(value) for value in must_cite)
    for offset, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            fail(f"{record_id}: claim_source_bindings[{offset}] must be an object")
        point_index = binding.get("expected_point_index")
        if not isinstance(point_index, int) or point_index not in expected_indexes:
            fail(f"{record_id}: binding has invalid expected_point_index={point_index!r}")
        if point_index in seen_indexes:
            fail(f"{record_id}: expected point {point_index} has duplicate bindings")
        seen_indexes.add(point_index)
        citations = binding.get("citations")
        if not isinstance(citations, list) or not citations:
            fail(f"{record_id}: expected point {point_index} must cite at least one source")
        unknown = set(str(value) for value in citations) - allowed
        if unknown:
            fail(f"{record_id}: expected point {point_index} cites outside must_cite: {sorted(unknown)}")

    if seen_indexes != expected_indexes:
        fail(f"{record_id}: not every expected point has exactly one source binding")


def validate_manifest(path: pathlib.Path) -> int:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    dataset = manifest.get("dataset")
    if not isinstance(dataset, str) or not dataset:
        fail(f"{path}: missing dataset")
    dataset_path = ROOT / dataset
    rows = load_jsonl(dataset_path)
    for row in rows:
        validate_record(row)
    return len(rows)


def self_test() -> None:
    good = {
        "id": "good",
        "expected_points": ["a", "b"],
        "must_cite": ["doi:10.test/a", "doi:10.test/b"],
        "claim_source_bindings": [
            {"expected_point_index": 0, "citations": ["doi:10.test/a"]},
            {"expected_point_index": 1, "citations": ["doi:10.test/b"]},
        ],
    }
    validate_record(good)
    for bad in (
        {**good, "claim_source_bindings": None},
        {**good, "claim_source_bindings": [{"expected_point_index": 0, "citations": ["doi:10.test/a"]}]},
        {**good, "claim_source_bindings": [
            {"expected_point_index": 0, "citations": ["doi:10.test/a"]},
            {"expected_point_index": 1, "citations": ["doi:10.test/outside"]},
        ]},
    ):
        try:
            validate_record(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid claim binding fixture should fail")
    print("model eval claim-binding self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="*")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
            return 0
        if not args.manifest:
            fail("at least one candidate manifest is required")
        total = 0
        for value in args.manifest:
            total += validate_manifest(pathlib.Path(value))
        print(f"model eval claim bindings: PASS ({total} records)")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, AssertionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
