#!/usr/bin/env python3
"""Freeze Grow Doc training-eligible artifacts with deterministic SHA-256 metadata.

This script does not alter canonical RAG data or choose a model checkpoint. It records the
exact strong-evidence SFT/GQA files used by a training experiment so later base+RAG and QLoRA
comparisons can prove they consumed the same supervision snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "model_tuning/generated/training_eligible"
DEFAULT_MANIFEST = DEFAULT_DIR / "snapshot_manifest.json"
ARTIFACTS = ("sft_v1.jsonl", "grounded_qa_v1.jsonl")


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_rows(path: pathlib.Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            count += 1
    return count


def git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def build_manifest(directory: pathlib.Path, revision: str) -> dict:
    artifacts = []
    for name in ARTIFACTS:
        path = directory / name
        if not path.is_file():
            raise FileNotFoundError(f"missing training artifact: {path}")
        artifacts.append(
            {
                "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "jsonl_rows": jsonl_rows(path),
            }
        )
    return {
        "schema_version": "grow-doc-training-snapshot-v1",
        "policy": {
            "rag_first": True,
            "purpose": "reproducible supervision identity for controlled base+RAG and QLoRA comparisons",
            "checkpoint_selection_from_protected_eval": False,
        },
        "git_revision": revision,
        "artifacts": artifacts,
        "total_examples": sum(item["jsonl_rows"] for item in artifacts),
    }


def self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        directory = pathlib.Path(tmp)
        (directory / "sft_v1.jsonl").write_text('{"id":"a"}\n{"id":"b"}\n', encoding="utf-8")
        (directory / "grounded_qa_v1.jsonl").write_text('{"id":"c"}\n', encoding="utf-8")
        manifest = build_manifest(directory, "deadbeef")
        assert manifest["git_revision"] == "deadbeef"
        assert manifest["total_examples"] == 3
        assert [x["jsonl_rows"] for x in manifest["artifacts"]] == [2, 1]
        assert all(len(x["sha256"]) == 64 for x in manifest["artifacts"])
    print("training snapshot freeze self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze exact Grow Doc training supervision identity.")
    parser.add_argument("--dir", type=pathlib.Path, default=DEFAULT_DIR)
    parser.add_argument("--manifest", type=pathlib.Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--revision", default=None)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        manifest = build_manifest(args.dir, args.revision or git_revision())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if not args.check_only:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("training snapshot freeze: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
