#!/usr/bin/env python3
"""Materialize a reviewed Heldout-v3 benchmark from the validated promotion preview.

This tool is intentionally explicit: it reuses the fail-closed preview validator, strips
candidate workflow control fields, preserves evidence/citation metadata, and writes a
stable JSONL artifact. It does not modify training data or model weights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build-heldout-v3-promotion-preview.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("heldout_v3_builder", BUILDER)
    if spec is None or spec.loader is None:
        raise SystemExit("unable to load heldout-v3 promotion builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    builder = load_builder()
    base = builder.load_jsonl(builder.BASE)
    final = builder.load_jsonl(builder.FINAL)
    reviews = json.loads(builder.REVIEW.read_text(encoding="utf-8"))
    rows = base + final
    builder.validate(rows, final, reviews)

    frozen = []
    for row in rows:
        item = dict(row)
        item.pop("candidate_status", None)
        item.pop("promotion_eligible", None)
        frozen.append(item)

    rendered = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in frozen
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    if args.manifest:
        source_ids = sorted({
            (row.get("source_metadata") or {}).get("source_id") for row in frozen
            if (row.get("source_metadata") or {}).get("source_id")
        })
        manifest = {
            "artifact": str(args.output),
            "sha256": digest,
            "cases": len(frozen),
            "categories": sorted({row["category"] for row in frozen}),
            "source_ids": source_ids,
            "policy": "frozen_evaluation_only_never_training",
        }
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Heldout-v3 frozen artifact: cases={len(frozen)} sha256={digest}")


if __name__ == "__main__":
    main()
