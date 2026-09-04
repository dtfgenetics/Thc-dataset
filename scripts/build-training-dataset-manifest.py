#!/usr/bin/env python3
"""Build a deterministic manifest for leak-safe Grow Doc training inputs.

The manifest binds materialized train/dev SFT and grounded-QA splits to the split
manifest, retrieval/quarantine corpora, and held-out benchmark. It rejects source
leakage and grounded-QA over-allocation before compute is spent.

This script validates/materializes metadata only. It does not train or merge models.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_MAX_GROUNDED_QA_FRACTION = 0.20


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


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


def summarize_jsonl(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    rows = load_jsonl(path)
    sources: set[str] = set()
    provenance_rows = 0
    context_required_rows = 0
    for row in rows:
        row_sources = collect_source_ids(row)
        sources.update(row_sources)
        provenance_rows += bool(row_sources)
        context_required_rows += row.get("context_required") is True
    return {
        "path": path.as_posix(),
        "sha256": digest(data),
        "bytes": len(data),
        "rows": len(rows),
        "source_ids": sorted(sources),
        "rows_with_source_ids": provenance_rows,
        "context_required_rows": context_required_rows,
    }


def require_qa_grounding(summary: dict[str, Any], label: str) -> None:
    rows = summary["rows"]
    if rows and summary["rows_with_source_ids"] != rows:
        raise ValueError(f"every {label} row must preserve source identifiers")
    if rows and summary["context_required_rows"] != rows:
        raise ValueError(f"every {label} row must remain context_required=true")


def build_manifest(
    *,
    train_sft: Path,
    dev_sft: Path,
    train_grounded_qa: Path,
    dev_grounded_qa: Path,
    retrieval: Path,
    quarantine: Path,
    heldout: Path,
    split_manifest: Path,
    max_grounded_qa_fraction: float,
) -> dict[str, Any]:
    if not 0 < max_grounded_qa_fraction <= 1:
        raise ValueError("max grounded-QA fraction must be > 0 and <= 1")

    datasets = {
        "train_sft": summarize_jsonl(train_sft),
        "dev_sft": summarize_jsonl(dev_sft),
        "train_grounded_qa": summarize_jsonl(train_grounded_qa),
        "dev_grounded_qa": summarize_jsonl(dev_grounded_qa),
        "retrieval": summarize_jsonl(retrieval),
        "quarantine": summarize_jsonl(quarantine),
        "heldout": summarize_jsonl(heldout),
    }
    split = load_json(split_manifest)

    expected_hashes = {
        "train_sft_sha256": datasets["train_sft"]["sha256"],
        "dev_sft_sha256": datasets["dev_sft"]["sha256"],
        "train_grounded_qa_sha256": datasets["train_grounded_qa"]["sha256"],
        "dev_grounded_qa_sha256": datasets["dev_grounded_qa"]["sha256"],
    }
    for key, actual in expected_hashes.items():
        expected = split.get(key)
        if expected != actual:
            raise ValueError(f"split manifest {key} does not match materialized dataset")

    train_rows = datasets["train_sft"]["rows"] + datasets["train_grounded_qa"]["rows"]
    if train_rows <= 0:
        raise ValueError("training mixture is empty")
    qa_fraction = datasets["train_grounded_qa"]["rows"] / train_rows
    if qa_fraction > max_grounded_qa_fraction + 1e-12:
        raise ValueError(
            f"grounded-QA training fraction {qa_fraction:.6f} exceeds cap "
            f"{max_grounded_qa_fraction:.6f}"
        )

    require_qa_grounding(datasets["train_grounded_qa"], "train grounded-QA")
    require_qa_grounding(datasets["dev_grounded_qa"], "dev grounded-QA")

    train_sources = set(datasets["train_sft"]["source_ids"]) | set(datasets["train_grounded_qa"]["source_ids"])
    dev_sources = set(datasets["dev_sft"]["source_ids"]) | set(datasets["dev_grounded_qa"]["source_ids"])
    heldout_sources = set(datasets["heldout"]["source_ids"])

    train_dev_overlap = sorted(train_sources & dev_sources)
    if train_dev_overlap:
        raise ValueError("source leakage across train/dev: " + ", ".join(train_dev_overlap))
    heldout_overlap = sorted((train_sources | dev_sources) & heldout_sources)
    if heldout_overlap:
        raise ValueError("held-out source leakage into train/dev: " + ", ".join(heldout_overlap))

    manifest = {
        "schema_version": "grow-doc-training-dataset-manifest-v2",
        "policy": {
            "max_grounded_qa_fraction": max_grounded_qa_fraction,
            "train_dev_source_overlap": 0,
            "heldout_training_source_overlap": 0,
            "require_grounded_qa_source_ids": True,
            "require_grounded_qa_context": True,
        },
        "mixture": {
            "train_sft_rows": datasets["train_sft"]["rows"],
            "train_grounded_qa_rows": datasets["train_grounded_qa"]["rows"],
            "training_rows": train_rows,
            "grounded_qa_fraction": round(qa_fraction, 12),
        },
        "split_manifest": {
            "path": split_manifest.as_posix(),
            "sha256": digest(split_manifest.read_bytes()),
            "schema_version": split.get("schema_version"),
            "algorithm": split.get("algorithm"),
            "seed": split.get("seed"),
        },
        "datasets": datasets,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["manifest_sha256"] = digest(canonical)
    return manifest


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = {
            name: root / f"{name}.jsonl"
            for name in (
                "train_sft",
                "dev_sft",
                "train_grounded_qa",
                "dev_grounded_qa",
                "retrieval",
                "quarantine",
                "heldout",
            )
        }
        write_jsonl(paths["train_sft"], [{"id": f"s{i}", "source_ids": [f"TRAIN-{i}"], "context_required": True} for i in range(8)])
        write_jsonl(paths["dev_sft"], [{"id": "ds1", "source_ids": ["DEV-1"], "context_required": True}])
        write_jsonl(paths["train_grounded_qa"], [
            {"id": "q1", "source_ids": ["QA-1"], "must_cite": ["QA-1"], "context_required": True},
            {"id": "q2", "source_ids": ["QA-2"], "must_cite": ["QA-2"], "context_required": True},
        ])
        write_jsonl(paths["dev_grounded_qa"], [
            {"id": "dq1", "source_ids": ["DEV-QA-1"], "must_cite": ["DEV-QA-1"], "context_required": True}
        ])
        write_jsonl(paths["retrieval"], [{"id": "r1", "source_ids": ["HELD-1"]}])
        write_jsonl(paths["quarantine"], [{"id": "x1", "source_ids": ["LOW-1"]}])
        write_jsonl(paths["heldout"], [{"id": "e1", "source_ids": ["HELD-1"]}])

        split_path = root / "split_manifest_v1.json"
        split = {
            "schema_version": "grow-doc-model-split-v1",
            "algorithm": "source-component-v1",
            "seed": 420,
            "train_sft_sha256": digest(paths["train_sft"].read_bytes()),
            "dev_sft_sha256": digest(paths["dev_sft"].read_bytes()),
            "train_grounded_qa_sha256": digest(paths["train_grounded_qa"].read_bytes()),
            "dev_grounded_qa_sha256": digest(paths["dev_grounded_qa"].read_bytes()),
        }
        split_path.write_text(json.dumps(split, sort_keys=True) + "\n", encoding="utf-8")

        manifest = build_manifest(**paths, split_manifest=split_path, max_grounded_qa_fraction=0.20)
        assert manifest["mixture"]["training_rows"] == 10
        assert manifest["mixture"]["grounded_qa_fraction"] == 0.2
        assert len(manifest["manifest_sha256"]) == 64
        again = build_manifest(**paths, split_manifest=split_path, max_grounded_qa_fraction=0.20)
        assert manifest["manifest_sha256"] == again["manifest_sha256"]

        # Keep QA at/below the cap so held-out leakage is the first policy violation.
        bad_train = [
            {"id": f"s{i}", "source_ids": [f"TRAIN-{i}"], "context_required": True} for i in range(8)
        ] + [{"id": "bad", "source_ids": ["HELD-1"], "context_required": True}]
        write_jsonl(paths["train_sft"], bad_train)
        split["train_sft_sha256"] = digest(paths["train_sft"].read_bytes())
        split_path.write_text(json.dumps(split, sort_keys=True) + "\n", encoding="utf-8")
        try:
            build_manifest(**paths, split_manifest=split_path, max_grounded_qa_fraction=0.20)
        except ValueError as exc:
            assert "held-out source leakage" in str(exc)
        else:
            raise AssertionError("held-out leakage was not rejected")

        write_jsonl(paths["train_sft"], [{"id": "s1", "source_ids": ["TRAIN-1"], "context_required": True}])
        split["train_sft_sha256"] = digest(paths["train_sft"].read_bytes())
        split_path.write_text(json.dumps(split, sort_keys=True) + "\n", encoding="utf-8")
        try:
            build_manifest(**paths, split_manifest=split_path, max_grounded_qa_fraction=0.20)
        except ValueError as exc:
            assert "exceeds cap" in str(exc)
        else:
            raise AssertionError("grounded-QA over-allocation was not rejected")

        # A materialized split changed without updating the split manifest must fail.
        write_jsonl(paths["train_sft"], [{"id": f"z{i}", "source_ids": [f"TRAIN-Z-{i}"], "context_required": True} for i in range(8)])
        try:
            build_manifest(**paths, split_manifest=split_path, max_grounded_qa_fraction=0.20)
        except ValueError as exc:
            assert "does not match materialized dataset" in str(exc)
        else:
            raise AssertionError("split hash mismatch was not rejected")

    print("training dataset manifest self-test: ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-sft", type=Path)
    parser.add_argument("--dev-sft", type=Path)
    parser.add_argument("--train-grounded-qa", type=Path)
    parser.add_argument("--dev-grounded-qa", type=Path)
    parser.add_argument("--retrieval", type=Path)
    parser.add_argument("--quarantine", type=Path)
    parser.add_argument("--heldout", type=Path)
    parser.add_argument("--split-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-grounded-qa-fraction", type=float, default=DEFAULT_MAX_GROUNDED_QA_FRACTION)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    required = [
        args.train_sft,
        args.dev_sft,
        args.train_grounded_qa,
        args.dev_grounded_qa,
        args.retrieval,
        args.quarantine,
        args.heldout,
        args.split_manifest,
    ]
    if any(path is None for path in required):
        parser.error(
            "--train-sft, --dev-sft, --train-grounded-qa, --dev-grounded-qa, "
            "--retrieval, --quarantine, --heldout, and --split-manifest are required"
        )

    manifest = build_manifest(
        train_sft=args.train_sft,
        dev_sft=args.dev_sft,
        train_grounded_qa=args.train_grounded_qa,
        dev_grounded_qa=args.dev_grounded_qa,
        retrieval=args.retrieval,
        quarantine=args.quarantine,
        heldout=args.heldout,
        split_manifest=args.split_manifest,
        max_grounded_qa_fraction=args.max_grounded_qa_fraction,
    )
    if args.check_only:
        print(json.dumps({
            "manifest_sha256": manifest["manifest_sha256"],
            "mixture": manifest["mixture"],
            "split_manifest": manifest["split_manifest"],
        }, sort_keys=True))
        return
    if args.output is None:
        parser.error("--output is required unless --check-only or --self-test is used")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({manifest['manifest_sha256']})")


if __name__ == "__main__":
    main()
