#!/usr/bin/env python3
"""Build a deterministic manifest for Grow Doc model-training inputs.

The manifest freezes exact file hashes/counts and checks two policy boundaries before
compute is spent: held-out source families must not leak into training inputs, and
grounded-QA must remain within its configured mixture cap.

This script does not train a model or imply that generated datasets exist in git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_MAX_GROUNDED_QA_FRACTION = 0.20


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        rows.append(value)
    return rows


def collect_source_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_l = str(key).lower()
            if key_l in {"source_id", "sourceid"} and isinstance(child, str) and child.strip():
                found.add(child.strip())
            elif key_l in {"source_ids", "sourceids", "must_cite"} and isinstance(child, list):
                found.update(str(item).strip() for item in child if str(item).strip())
            found.update(collect_source_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(collect_source_ids(child))
    return found


def summarize(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    rows = load_jsonl(path)
    source_ids: set[str] = set()
    context_required = 0
    provenance_rows = 0
    for row in rows:
        ids = collect_source_ids(row)
        source_ids.update(ids)
        if row.get("context_required") is True:
            context_required += 1
        if ids:
            provenance_rows += 1
    return {
        "path": path.as_posix(),
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "rows": len(rows),
        "source_ids": sorted(source_ids),
        "rows_with_source_ids": provenance_rows,
        "context_required_rows": context_required,
    }


def build_manifest(
    *,
    sft: Path,
    grounded_qa: Path,
    retrieval: Path,
    quarantine: Path,
    heldout: Path,
    max_grounded_qa_fraction: float,
) -> dict[str, Any]:
    if not 0 < max_grounded_qa_fraction <= 1:
        raise ValueError("max grounded-QA fraction must be > 0 and <= 1")

    datasets = {
        "sft": summarize(sft),
        "grounded_qa": summarize(grounded_qa),
        "retrieval": summarize(retrieval),
        "quarantine": summarize(quarantine),
        "heldout": summarize(heldout),
    }

    train_rows = datasets["sft"]["rows"] + datasets["grounded_qa"]["rows"]
    if train_rows <= 0:
        raise ValueError("training mixture is empty")
    qa_fraction = datasets["grounded_qa"]["rows"] / train_rows
    if qa_fraction > max_grounded_qa_fraction + 1e-12:
        raise ValueError(
            f"grounded-QA fraction {qa_fraction:.6f} exceeds cap {max_grounded_qa_fraction:.6f}"
        )

    heldout_sources = set(datasets["heldout"]["source_ids"])
    training_sources = set(datasets["sft"]["source_ids"]) | set(datasets["grounded_qa"]["source_ids"])
    leakage = sorted(heldout_sources & training_sources)
    if leakage:
        raise ValueError("held-out source leakage into training inputs: " + ", ".join(leakage))

    qa_rows = datasets["grounded_qa"]["rows"]
    if qa_rows and datasets["grounded_qa"]["rows_with_source_ids"] != qa_rows:
        raise ValueError("every grounded-QA row must preserve source identifiers")
    if qa_rows and datasets["grounded_qa"]["context_required_rows"] != qa_rows:
        raise ValueError("every grounded-QA row must remain context_required=true")

    manifest = {
        "schema_version": 1,
        "policy": {
            "max_grounded_qa_fraction": max_grounded_qa_fraction,
            "heldout_training_source_overlap": 0,
            "require_grounded_qa_source_ids": True,
            "require_grounded_qa_context": True,
        },
        "mixture": {
            "sft_rows": datasets["sft"]["rows"],
            "grounded_qa_rows": datasets["grounded_qa"]["rows"],
            "training_rows": train_rows,
            "grounded_qa_fraction": round(qa_fraction, 12),
        },
        "datasets": datasets,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["manifest_sha256"] = sha256_bytes(canonical)
    return manifest


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = {name: root / f"{name}.jsonl" for name in ("sft", "grounded_qa", "retrieval", "quarantine", "heldout")}
        write_jsonl(paths["sft"], [{"id": f"s{i}", "source_ids": [f"TRAIN-{i}"]} for i in range(8)])
        write_jsonl(paths["grounded_qa"], [
            {"id": "q1", "source_ids": ["QA-1"], "must_cite": ["QA-1"], "context_required": True},
            {"id": "q2", "source_ids": ["QA-2"], "must_cite": ["QA-2"], "context_required": True},
        ])
        write_jsonl(paths["retrieval"], [{"id": "r1", "source_ids": ["HELD-1"]}])
        write_jsonl(paths["quarantine"], [{"id": "x1", "source_ids": ["LOW-1"]}])
        write_jsonl(paths["heldout"], [{"id": "e1", "source_ids": ["HELD-1"]}])

        manifest = build_manifest(**paths, max_grounded_qa_fraction=0.20)
        assert manifest["mixture"]["training_rows"] == 10
        assert manifest["mixture"]["grounded_qa_fraction"] == 0.2
        assert len(manifest["manifest_sha256"]) == 64

        # The manifest must be stable for identical bytes.
        again = build_manifest(**paths, max_grounded_qa_fraction=0.20)
        assert manifest["manifest_sha256"] == again["manifest_sha256"]

        # Held-out material may exist in retrieval, but never in SFT/grounded-QA.
        write_jsonl(paths["sft"], [{"id": "bad", "source_ids": ["HELD-1"]}])
        try:
            build_manifest(**paths, max_grounded_qa_fraction=0.20)
        except ValueError as exc:
            assert "held-out source leakage" in str(exc)
        else:
            raise AssertionError("held-out leakage was not rejected")

        # Restore SFT and prove the mixture cap is enforced.
        write_jsonl(paths["sft"], [{"id": "s1", "source_ids": ["TRAIN-1"]}])
        try:
            build_manifest(**paths, max_grounded_qa_fraction=0.20)
        except ValueError as exc:
            assert "exceeds cap" in str(exc)
        else:
            raise AssertionError("grounded-QA over-allocation was not rejected")

    print("training dataset manifest self-test: ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sft", type=Path)
    parser.add_argument("--grounded-qa", type=Path)
    parser.add_argument("--retrieval", type=Path)
    parser.add_argument("--quarantine", type=Path)
    parser.add_argument("--heldout", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-grounded-qa-fraction", type=float, default=DEFAULT_MAX_GROUNDED_QA_FRACTION)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    required = [args.sft, args.grounded_qa, args.retrieval, args.quarantine, args.heldout]
    if any(path is None for path in required):
        parser.error("--sft, --grounded-qa, --retrieval, --quarantine, and --heldout are required")

    manifest = build_manifest(
        sft=args.sft,
        grounded_qa=args.grounded_qa,
        retrieval=args.retrieval,
        quarantine=args.quarantine,
        heldout=args.heldout,
        max_grounded_qa_fraction=args.max_grounded_qa_fraction,
    )
    if args.check_only:
        print(json.dumps({"manifest_sha256": manifest["manifest_sha256"], "mixture": manifest["mixture"]}, sort_keys=True))
        return
    if args.output is None:
        parser.error("--output is required unless --check-only or --self-test is used")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({manifest['manifest_sha256']})")


if __name__ == "__main__":
    main()
