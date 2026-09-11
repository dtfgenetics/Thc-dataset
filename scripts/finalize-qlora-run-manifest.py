#!/usr/bin/env python3
"""Bind a Grow Doc QLoRA run manifest to the exact saved adapter bytes.

This is deliberately a post-save, pre-evaluation gate. It calls the canonical
adapter hasher, validates the returned SHA-256, and writes it into the run
manifest without changing promotion state.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HASHER = ROOT / "scripts/hash-adapter-artifact.py"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def adapter_digest(adapter_dir: Path) -> str:
    raw = subprocess.check_output(
        [sys.executable, str(HASHER), str(adapter_dir), "--json"],
        cwd=ROOT,
        text=True,
    )
    payload = json.loads(raw)
    digest = payload.get("adapter_artifact_sha256", "")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise RuntimeError("canonical adapter hasher returned an invalid SHA-256")
    return digest


def finalize(manifest_path: Path, adapter_dir: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("training run manifest must be a JSON object")
    if manifest.get("status") != "trained_not_promoted":
        raise ValueError("only trained_not_promoted manifests may be finalized")
    if manifest.get("promotion_eligible") is not False:
        raise ValueError("finalization must not promote an adapter")
    if manifest.get("adapter_merge_performed") is not False:
        raise ValueError("finalization refuses a manifest that reports an adapter merge")
    if manifest.get("deployment_performed") is not False:
        raise ValueError("finalization refuses a manifest that reports deployment")

    digest = adapter_digest(adapter_dir)
    existing = manifest.get("adapter_artifact_sha256")
    if existing is not None and existing != digest:
        raise ValueError(
            "existing adapter_artifact_sha256 does not match current adapter bytes"
        )

    manifest["adapter_artifact_sha256"] = digest
    manifest["adapter_path"] = str(adapter_dir)
    manifest["artifact_identity_scheme"] = "grow-doc-adapter-tree-sha256-v1"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        adapter = root / "adapter"
        adapter.mkdir()
        (adapter / "adapter_config.json").write_text('{"r":32}\n', encoding="utf-8")
        (adapter / "adapter_model.safetensors").write_bytes(b"grow-doc-test-adapter")
        manifest_path = root / "training-run-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "grow-doc-qlora-run-v1",
                    "status": "trained_not_promoted",
                    "promotion_eligible": False,
                    "adapter_merge_performed": False,
                    "deployment_performed": False,
                }
            ) + "\n",
            encoding="utf-8",
        )
        first = finalize(manifest_path, adapter)
        assert SHA256.fullmatch(first["adapter_artifact_sha256"])
        assert first["promotion_eligible"] is False
        assert first["adapter_merge_performed"] is False
        assert first["deployment_performed"] is False

        # Idempotent for unchanged bytes.
        second = finalize(manifest_path, adapter)
        assert second["adapter_artifact_sha256"] == first["adapter_artifact_sha256"]

        # Fail closed if bytes drift after identity has been recorded.
        (adapter / "adapter_model.safetensors").write_bytes(b"mutated")
        try:
            finalize(manifest_path, adapter)
        except ValueError as exc:
            assert "does not match" in str(exc)
        else:
            raise AssertionError("adapter-byte drift was not rejected")

    print("Grow Doc QLoRA manifest finalizer self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("adapter_dir", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.manifest is None or args.adapter_dir is None:
        parser.error("manifest and adapter_dir are required unless --self-test is used")
    manifest = finalize(args.manifest, args.adapter_dir)
    print(manifest["adapter_artifact_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
