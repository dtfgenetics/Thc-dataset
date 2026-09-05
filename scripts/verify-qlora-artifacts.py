#!/usr/bin/env python3
"""Verify QLoRA config hashes against materialized training artifacts.

This is intentionally dependency-free. It does not train or load a model; it
only proves that the configured immutable SHA-256 values match the exact bytes
of the generated split and training-dataset manifests.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "model_tuning/config/qlora_8b.yaml"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([^#\n]+?)\s*$", text)
    return match.group(1).strip().strip('"\'') if match else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(config_path: Path, *, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not config_path.exists():
        return [f"config not found: {config_path}"]
    text = config_path.read_text(encoding="utf-8")
    checks = (
        ("split_manifest_path", "split_manifest_sha256"),
        ("dataset_manifest_path", "dataset_manifest_sha256"),
    )
    for path_key, hash_key in checks:
        configured_path = scalar(text, path_key)
        expected = scalar(text, hash_key)
        if not configured_path:
            errors.append(f"{path_key} is required")
            continue
        if not expected or not HEX64.fullmatch(expected):
            errors.append(f"{hash_key} must be a pinned lowercase SHA-256")
            continue
        artifact = root / configured_path
        if not artifact.exists():
            errors.append(f"materialized artifact missing: {configured_path}")
            continue
        actual = sha256_file(artifact)
        if actual != expected:
            errors.append(f"{hash_key} mismatch for {configured_path}: expected {expected}, got {actual}")
    return errors


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "generated").mkdir()
        split = root / "generated/split.json"
        dataset = root / "generated/dataset.json"
        split.write_bytes(b'{"split":1}\n')
        dataset.write_bytes(b'{"dataset":1}\n')
        config = root / "qlora.yaml"
        config.write_text(
            "split_manifest_path: generated/split.json\n"
            f"split_manifest_sha256: {sha256_file(split)}\n"
            "dataset_manifest_path: generated/dataset.json\n"
            f"dataset_manifest_sha256: {sha256_file(dataset)}\n",
            encoding="utf-8",
        )
        assert not verify(config, root=root)
        dataset.write_bytes(b'{"dataset":2}\n')
        errors = verify(config, root=root)
        assert any("dataset_manifest_sha256 mismatch" in error for error in errors)
    print("QLoRA artifact verifier self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    errors = verify(args.config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("QLoRA artifact hashes match materialized bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
