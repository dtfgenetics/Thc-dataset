#!/usr/bin/env python3
"""Validate that a Grow Doc experiment is bound to one immutable input snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA = "grow-doc-experiment-freeze-v1"
TRAINING_SCHEMA = "grow-doc-training-snapshot-v1"
SHA_FIELDS = (
    "repository_revision",
    "model_revision",
    "tokenizer_revision",
    "benchmark_sha256",
    "retrieval_snapshot_sha256",
    "retrieval_manifest_sha256",
    "training_snapshot_manifest_sha256",
    "sft_sha256",
    "grounded_qa_sha256",
    "qlora_config_sha256",
)


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) in (40, 64) and all(c in "0123456789abcdef" for c in value.lower())


def load_json(path: pathlib.Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def artifact_map(training: dict) -> dict[str, dict]:
    return {pathlib.Path(item["path"]).name: item for item in training.get("artifacts", []) if isinstance(item, dict) and item.get("path")}


def validate_manifest(manifest: dict, root: pathlib.Path) -> None:
    if manifest.get("schema_version") != SCHEMA:
        raise ValueError(f"expected schema_version {SCHEMA}")
    for field in SHA_FIELDS:
        if not is_sha(manifest.get(field)):
            raise ValueError(f"{field} must be a pinned SHA/hash")

    paths = manifest.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("paths must be an object")
    required_paths = {
        "benchmark": "benchmark_sha256",
        "retrieval_snapshot": "retrieval_snapshot_sha256",
        "retrieval_manifest": "retrieval_manifest_sha256",
        "training_snapshot_manifest": "training_snapshot_manifest_sha256",
        "qlora_config": "qlora_config_sha256",
    }
    for key, hash_field in required_paths.items():
        rel = paths.get(key)
        if not isinstance(rel, str) or not rel:
            raise ValueError(f"missing paths.{key}")
        path = root / rel
        if not path.is_file():
            raise ValueError(f"missing frozen input: {rel}")
        if sha256(path) != manifest[hash_field]:
            raise ValueError(f"hash mismatch for {key}: {rel}")

    training_path = root / paths["training_snapshot_manifest"]
    training = load_json(training_path)
    if training.get("schema_version") != TRAINING_SCHEMA:
        raise ValueError("training snapshot schema mismatch")
    if training.get("git_revision") != manifest["repository_revision"]:
        raise ValueError("training snapshot repository revision mismatch")
    artifacts = artifact_map(training)
    for name, field in (("sft_v1.jsonl", "sft_sha256"), ("grounded_qa_v1.jsonl", "grounded_qa_sha256")):
        item = artifacts.get(name)
        if not item or item.get("sha256") != manifest[field]:
            raise ValueError(f"training artifact identity mismatch: {name}")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        for name, content in {
            "benchmark.jsonl": '{"id":"eval"}\n',
            "rag.jsonl": '{"id":"claim"}\n',
            "rag.manifest.json": '{"schema":"rag"}\n',
            "qlora.json": '{"lora_r":16}\n',
        }.items():
            (root / name).write_text(content, encoding="utf-8")
        revision = "a" * 40
        sft_hash = "b" * 64
        gqa_hash = "c" * 64
        training = {
            "schema_version": TRAINING_SCHEMA,
            "git_revision": revision,
            "artifacts": [
                {"path": "model_tuning/generated/training_eligible/sft_v1.jsonl", "sha256": sft_hash},
                {"path": "model_tuning/generated/training_eligible/grounded_qa_v1.jsonl", "sha256": gqa_hash},
            ],
        }
        training_path = root / "training.json"
        training_path.write_text(json.dumps(training), encoding="utf-8")
        manifest = {
            "schema_version": SCHEMA,
            "repository_revision": revision,
            "model_revision": "d" * 40,
            "tokenizer_revision": "d" * 40,
            "benchmark_sha256": sha256(root / "benchmark.jsonl"),
            "retrieval_snapshot_sha256": sha256(root / "rag.jsonl"),
            "retrieval_manifest_sha256": sha256(root / "rag.manifest.json"),
            "training_snapshot_manifest_sha256": sha256(training_path),
            "sft_sha256": sft_hash,
            "grounded_qa_sha256": gqa_hash,
            "qlora_config_sha256": sha256(root / "qlora.json"),
            "paths": {
                "benchmark": "benchmark.jsonl",
                "retrieval_snapshot": "rag.jsonl",
                "retrieval_manifest": "rag.manifest.json",
                "training_snapshot_manifest": "training.json",
                "qlora_config": "qlora.json",
            },
        }
        validate_manifest(manifest, root)
        broken = dict(manifest)
        broken["benchmark_sha256"] = "0" * 64
        try:
            validate_manifest(broken, root)
        except ValueError as exc:
            assert "hash mismatch for benchmark" in str(exc)
        else:
            raise AssertionError("tampered benchmark must fail")
        broken = dict(manifest)
        broken["sft_sha256"] = "0" * 64
        try:
            validate_manifest(broken, root)
        except ValueError as exc:
            assert "training artifact identity mismatch" in str(exc)
        else:
            raise AssertionError("mismatched SFT identity must fail")
    print("Grow Doc experiment freeze validator self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=pathlib.Path)
    parser.add_argument("--root", type=pathlib.Path, default=ROOT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.manifest is None:
        parser.error("manifest is required unless --self-test is used")
    try:
        validate_manifest(load_json(args.manifest), args.root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Grow Doc experiment freeze validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
