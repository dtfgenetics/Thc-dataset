#!/usr/bin/env python3
"""Run adapter evaluation only when its frozen training snapshot is provable.

This wrapper deliberately keeps factual knowledge in the RAG path while binding any
QLoRA/LoRA adapter evaluation to the exact strong-evidence SFT/GQA snapshot used to
train it. It fails closed before invoking the model evaluator and validates the emitted
run manifest again after attaching derived training provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

SNAPSHOT_SCHEMA = "grow-doc-training-snapshot-v1"
REQUIRED = {"sft_v1.jsonl": "sft_sha256", "grounded_qa_v1.jsonl": "grounded_qa_sha256"}


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def derive_provenance(snapshot_path: pathlib.Path) -> dict[str, str]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
        raise ValueError("unsupported training snapshot schema")
    revision = snapshot.get("git_revision")
    if not isinstance(revision, str) or len(revision) < 7:
        raise ValueError("training snapshot requires a pinned git_revision")
    artifacts = snapshot.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("training snapshot artifacts must be a list")
    by_name: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError("training snapshot artifact must be an object")
        name = pathlib.PurePosixPath(str(item.get("path", ""))).name
        if name in by_name:
            raise ValueError(f"duplicate training snapshot artifact: {name}")
        by_name[name] = item
    provenance = {
        "snapshot_manifest_sha256": sha256(snapshot_path),
        "training_git_revision": revision,
    }
    for name, key in REQUIRED.items():
        if name not in by_name:
            raise ValueError(f"training snapshot missing required artifact: {name}")
        digest = by_name[name].get("sha256")
        if not is_sha(digest):
            raise ValueError(f"training snapshot has invalid SHA-256 for {name}")
        provenance[key] = digest.lower()
    return provenance


def attach_and_validate(manifest_path: pathlib.Path, snapshot_path: pathlib.Path, validator: pathlib.Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    adapter = manifest.get("model", {}).get("adapter")
    if not isinstance(adapter, dict) or not adapter.get("repository"):
        raise ValueError("provenance-bound launcher requires an adapter evaluation")
    revision = adapter.get("revision")
    if not isinstance(revision, str) or revision in ("", "UNPINNED") or len(revision) < 7:
        raise ValueError("adapter revision must be pinned")
    manifest["training_provenance"] = derive_provenance(snapshot_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, str(validator), "--run-manifest", str(manifest_path), "--training-snapshot", str(snapshot_path)],
        check=True,
    )


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        snapshot = root / "snapshot.json"
        snapshot.write_text(json.dumps({
            "schema_version": SNAPSHOT_SCHEMA,
            "git_revision": "abcdef1234567",
            "artifacts": [
                {"path": "generated/sft_v1.jsonl", "sha256": "1" * 64},
                {"path": "generated/grounded_qa_v1.jsonl", "sha256": "2" * 64},
            ],
        }), encoding="utf-8")
        p = derive_provenance(snapshot)
        assert p["training_git_revision"] == "abcdef1234567"
        assert p["sft_sha256"] == "1" * 64
        assert p["grounded_qa_sha256"] == "2" * 64
        assert p["snapshot_manifest_sha256"] == sha256(snapshot)
        bad = root / "bad.json"
        bad.write_text(json.dumps({"schema_version": SNAPSHOT_SCHEMA, "git_revision": "abcdef1", "artifacts": []}), encoding="utf-8")
        try:
            derive_provenance(bad)
        except ValueError as exc:
            assert "missing required artifact" in str(exc)
        else:
            raise AssertionError("incomplete training snapshot must be rejected")
    print("provenance-bound adapter eval self-test: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--training-snapshot", type=pathlib.Path)
    p.add_argument("--output-dir", type=pathlib.Path)
    p.add_argument("evaluator_args", nargs=argparse.REMAINDER)
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.training_snapshot is None or args.output_dir is None:
        p.error("--training-snapshot and --output-dir are required")
    if not args.training_snapshot.is_file():
        p.error("--training-snapshot must name an existing frozen manifest")
    # Validate snapshot before any model process is started.
    derive_provenance(args.training_snapshot)
    script_dir = pathlib.Path(__file__).resolve().parent
    evaluator = script_dir / "run-model-eval.py"
    validator = script_dir / "validate-adapter-training-provenance.py"
    forwarded = list(args.evaluator_args)
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]
    if "--adapter-repo" not in forwarded or "--adapter-revision" not in forwarded:
        p.error("adapter repo and pinned adapter revision are required")
    subprocess.run([sys.executable, str(evaluator), "--output-dir", str(args.output_dir), *forwarded], check=True)
    attach_and_validate(args.output_dir / "run-manifest.json", args.training_snapshot, validator)
    print("provenance-bound adapter evaluation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
