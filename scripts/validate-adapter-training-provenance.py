#!/usr/bin/env python3
"""Fail closed when a tuned Grow Doc evaluation cannot prove its training snapshot.

Base-model evaluations do not require training provenance. Adapter evaluations must bind
an immutable adapter revision to the exact frozen strong-evidence supervision manifest
used for training. This keeps base+RAG versus QLoRA comparisons attributable to model
changes instead of silent dataset drift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import tempfile
from typing import Any

REQUIRED_ARTIFACTS = ("sft_v1.jsonl", "grounded_qa_v1.jsonl")
SNAPSHOT_SCHEMA = "grow-doc-training-snapshot-v1"


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def artifact_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = snapshot.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("training snapshot artifacts must be a list")
    mapped: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError("training snapshot artifact must be an object")
        name = pathlib.PurePosixPath(str(item.get("path", ""))).name
        if name in mapped:
            raise ValueError(f"duplicate training snapshot artifact: {name}")
        mapped[name] = item
    return mapped


def validate(run: dict[str, Any], snapshot_path: pathlib.Path | None) -> None:
    model = run.get("model")
    if not isinstance(model, dict):
        raise ValueError("run manifest model must be an object")
    adapter = model.get("adapter")
    provenance = run.get("training_provenance")

    if adapter is None:
        if provenance is not None:
            raise ValueError("base-model evaluation must not claim adapter training provenance")
        return

    if not isinstance(adapter, dict) or not adapter.get("repository"):
        raise ValueError("adapter evaluation must identify adapter repository")
    revision = adapter.get("revision")
    if not isinstance(revision, str) or revision in ("", "UNPINNED") or len(revision) < 7:
        raise ValueError("adapter evaluation requires a pinned adapter revision")
    if not isinstance(provenance, dict):
        raise ValueError("adapter evaluation requires training_provenance")
    if snapshot_path is None or not snapshot_path.is_file():
        raise ValueError("adapter evaluation requires the frozen training snapshot manifest")

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
        raise ValueError("unsupported training snapshot schema")
    manifest_hash = provenance.get("snapshot_manifest_sha256")
    if not is_sha256(manifest_hash) or manifest_hash.lower() != sha256(snapshot_path):
        raise ValueError("training snapshot manifest SHA-256 mismatch")
    if provenance.get("training_git_revision") != snapshot.get("git_revision"):
        raise ValueError("training Git revision does not match frozen snapshot")

    artifacts = artifact_map(snapshot)
    for name in REQUIRED_ARTIFACTS:
        if name not in artifacts:
            raise ValueError(f"training snapshot missing required artifact: {name}")
        expected = artifacts[name].get("sha256")
        if not is_sha256(expected):
            raise ValueError(f"training snapshot has invalid SHA-256 for {name}")
        key = "sft_sha256" if name == "sft_v1.jsonl" else "grounded_qa_sha256"
        if provenance.get(key) != expected:
            raise ValueError(f"training provenance {key} does not match frozen snapshot")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        snapshot_path = root / "snapshot.json"
        sft_hash = "1" * 64
        gqa_hash = "2" * 64
        snapshot = {
            "schema_version": SNAPSHOT_SCHEMA,
            "git_revision": "abcdef1234567",
            "artifacts": [
                {"path": "model_tuning/generated/training_eligible/sft_v1.jsonl", "sha256": sft_hash},
                {"path": "model_tuning/generated/training_eligible/grounded_qa_v1.jsonl", "sha256": gqa_hash},
            ],
        }
        snapshot_path.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
        base = {"model": {"adapter": None}, "training_provenance": None}
        validate(base, None)
        tuned = {
            "model": {"adapter": {"repository": "org/adapter", "revision": "1234567"}},
            "training_provenance": {
                "snapshot_manifest_sha256": sha256(snapshot_path),
                "training_git_revision": "abcdef1234567",
                "sft_sha256": sft_hash,
                "grounded_qa_sha256": gqa_hash,
            },
        }
        validate(tuned, snapshot_path)
        failures = [
            ({**tuned, "training_provenance": None}, "training_provenance"),
            ({**tuned, "training_provenance": {**tuned["training_provenance"], "sft_sha256": "0" * 64}}, "sft_sha256"),
            ({"model": {"adapter": {"repository": "org/adapter", "revision": "UNPINNED"}}, "training_provenance": tuned["training_provenance"]}, "pinned"),
            ({"model": {"adapter": None}, "training_provenance": tuned["training_provenance"]}, "must not claim"),
        ]
        for candidate, expected in failures:
            try:
                validate(candidate, snapshot_path)
            except ValueError as exc:
                assert expected in str(exc), str(exc)
            else:
                raise AssertionError(f"expected rejection containing {expected!r}")
    print("adapter training provenance self-test: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-manifest", type=pathlib.Path)
    p.add_argument("--training-snapshot", type=pathlib.Path)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.run_manifest is None:
        p.error("--run-manifest is required unless --self-test is used")
    try:
        run = json.loads(args.run_manifest.read_text(encoding="utf-8"))
        validate(run, args.training_snapshot)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("adapter training provenance: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
