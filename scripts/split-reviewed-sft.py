#!/usr/bin/env python3
"""Create leakage-safe train/dev partitions from human-reviewed Grow Doc SFT JSONL.

This script does not create or modify locked evaluation data. It only partitions
records that have already been promoted to reviewStatus=reviewed.

Safety invariants:
- every input row must be human reviewed
- splitGroup is atomic across partitions
- stable record IDs are unique
- exact/normalized conversations cannot cross partitions
- normalized DOI/URL provenance identities cannot cross partitions
- optional locked-eval manifest blocks known record IDs and split groups
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    value = value.rstrip("/")
    return f"doi:{value}" if value else None


def doi_from_url(value: str | None) -> str | None:
    if not value:
        return None
    match = re.match(r"^https?://(?:dx\.)?doi\.org/(.+?)/?$", value.strip(), re.I)
    return normalize_doi(match.group(1)) if match else None


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"#.*$", "", value.strip()).rstrip("/").lower()
    return f"url:{value}" if value else None


def provenance_keys(row: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for source in row.get("provenance", []):
        doi = normalize_doi(source.get("doi")) or doi_from_url(source.get("url"))
        url = normalize_url(source.get("url"))
        if doi:
            keys.add(doi)
        if url and not url.startswith("url:https://doi.org/") and not url.startswith("url:http://doi.org/"):
            keys.add(url)
    return keys


def normalized_messages(row: dict[str, Any]) -> str:
    text = json.dumps(row["messages"], sort_keys=True, ensure_ascii=False)
    return re.sub(r"\s+", " ", text).strip().casefold()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def load_locked_manifest(path: Path | None) -> tuple[set[str], set[str]]:
    if path is None:
        return set(), set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("recordIds", [])), set(data.get("splitGroups", []))


def validate_rows(rows: list[dict[str, Any]], locked_ids: set[str], locked_groups: set[str]) -> None:
    if not rows:
        raise ValueError("reviewed corpus is empty")

    seen_ids: set[str] = set()
    for row in rows:
        rid = row.get("id")
        if not rid:
            raise ValueError("record missing id")
        if rid in seen_ids:
            raise ValueError(f"duplicate record id: {rid}")
        seen_ids.add(rid)

        if row.get("reviewStatus") != "reviewed":
            raise ValueError(f"record {rid} is not human reviewed")
        if not row.get("splitGroup"):
            raise ValueError(f"record {rid} missing splitGroup")
        if not row.get("provenance"):
            raise ValueError(f"record {rid} missing provenance")
        if rid in locked_ids:
            raise ValueError(f"record {rid} overlaps locked evaluation manifest")
        if row["splitGroup"] in locked_groups:
            raise ValueError(f"split group {row['splitGroup']} overlaps locked evaluation manifest")


def choose_dev_groups(groups: dict[str, list[dict[str, Any]]], dev_fraction: float, seed: str) -> set[str]:
    if not 0 < dev_fraction < 0.5:
        raise ValueError("dev_fraction must be between 0 and 0.5")
    if len(groups) < 2:
        raise ValueError("at least two independent split groups are required for train/dev partitioning")

    total = sum(len(v) for v in groups.values())
    target = max(1, round(total * dev_fraction))
    ordered = sorted(groups, key=lambda g: hashlib.sha256(f"{seed}|{g}".encode()).hexdigest())

    chosen: set[str] = set()
    chosen_count = 0
    for group in ordered:
        if len(chosen) >= len(groups) - 1:
            break
        size = len(groups[group])
        current_error = abs(target - chosen_count)
        new_error = abs(target - (chosen_count + size))
        if new_error < current_error:
            chosen.add(group)
            chosen_count += size

    if not chosen:
        smallest = min(ordered, key=lambda g: (len(groups[g]), hashlib.sha256(f"{seed}|{g}".encode()).hexdigest()))
        chosen.add(smallest)

    if len(chosen) == len(groups):
        chosen.remove(max(chosen, key=lambda g: len(groups[g])))
    return chosen


def assert_no_cross_split_leakage(train: list[dict[str, Any]], dev: list[dict[str, Any]]) -> None:
    train_groups = {r["splitGroup"] for r in train}
    dev_groups = {r["splitGroup"] for r in dev}
    overlap = train_groups & dev_groups
    if overlap:
        raise ValueError(f"splitGroup leakage across train/dev: {sorted(overlap)}")

    train_msgs = {normalized_messages(r) for r in train}
    dev_msgs = {normalized_messages(r) for r in dev}
    if train_msgs & dev_msgs:
        raise ValueError("normalized conversation duplicate crosses train/dev")

    train_sources = set().union(*(provenance_keys(r) for r in train))
    dev_sources = set().union(*(provenance_keys(r) for r in dev))
    source_overlap = train_sources & dev_sources
    if source_overlap:
        sample = sorted(source_overlap)[:5]
        raise ValueError(f"provenance source identity leakage across train/dev: {sample}")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--train-output", required=True)
    ap.add_argument("--dev-output", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--locked-manifest")
    ap.add_argument("--dev-fraction", type=float, default=0.15)
    ap.add_argument("--seed", default="growdoc-v1")
    args = ap.parse_args()

    rows = load_jsonl(Path(args.input))
    locked_ids, locked_groups = load_locked_manifest(Path(args.locked_manifest) if args.locked_manifest else None)
    validate_rows(rows, locked_ids, locked_groups)

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["splitGroup"]].append(row)

    dev_groups = choose_dev_groups(groups, args.dev_fraction, args.seed)
    train = [r for r in rows if r["splitGroup"] not in dev_groups]
    dev = [r for r in rows if r["splitGroup"] in dev_groups]
    assert_no_cross_split_leakage(train, dev)

    write_jsonl(Path(args.train_output), train)
    write_jsonl(Path(args.dev_output), dev)

    report = {
        "inputRecords": len(rows),
        "trainRecords": len(train),
        "devRecords": len(dev),
        "trainGroups": len({r["splitGroup"] for r in train}),
        "devGroups": len({r["splitGroup"] for r in dev}),
        "requestedDevFraction": args.dev_fraction,
        "actualDevFraction": round(len(dev) / len(rows), 6),
        "seed": args.seed,
        "lanesTrain": dict(sorted(Counter(r.get("lane", "unknown") for r in train).items())),
        "lanesDev": dict(sorted(Counter(r.get("lane", "unknown") for r in dev).items())),
        "lockedRecordIdsChecked": len(locked_ids),
        "lockedSplitGroupsChecked": len(locked_groups),
        "crossSplitLeakage": {
            "splitGroups": 0,
            "normalizedMessages": 0,
            "provenanceIdentities": 0
        }
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
