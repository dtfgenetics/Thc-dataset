#!/usr/bin/env python3
"""Deterministically content-address a Grow Doc LoRA/QLoRA adapter directory.

The digest is independent of filesystem traversal order and mtimes. It binds each
regular file by UTF-8 relative POSIX path, byte length, and SHA-256 content digest.
Symlinks and non-files are rejected so an adapter identity cannot depend on external
filesystem state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

HEX64 = set("0123456789abcdef")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def adapter_artifact_manifest(root: Path) -> list[dict[str, object]]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"adapter directory does not exist: {root}")

    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ValueError(f"symlinks are forbidden in adapter artifacts: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"non-regular adapter artifact entry: {path}")
        relative = path.relative_to(root).as_posix()
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    if not rows:
        raise ValueError(f"adapter directory is empty: {root}")
    return rows


def adapter_artifact_sha256(root: Path) -> str:
    manifest = adapter_artifact_manifest(root)
    canonical = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "nested").mkdir()
        (root / "adapter_config.json").write_text('{"r":32}\n', encoding="utf-8")
        (root / "nested" / "weights.bin").write_bytes(b"\x00\x01grow-doc")
        first = adapter_artifact_sha256(root)
        second = adapter_artifact_sha256(root)
        assert first == second
        assert len(first) == 64 and set(first) <= HEX64

        (root / "nested" / "weights.bin").write_bytes(b"\x00\x01grow-doc-v2")
        changed = adapter_artifact_sha256(root)
        assert changed != first

        mirror = root / "mirror"
        mirror.mkdir()
        (mirror / "nested").mkdir()
        (mirror / "nested" / "weights.bin").write_bytes(b"\x00\x01grow-doc-v2")
        (mirror / "adapter_config.json").write_text('{"r":32}\n', encoding="utf-8")
        assert adapter_artifact_sha256(mirror) == changed

    print("Grow Doc adapter artifact hash self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("adapter_dir", type=Path, nargs="?")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if args.adapter_dir is None:
        parser.error("adapter_dir is required unless --self-test is used")

    manifest = adapter_artifact_manifest(args.adapter_dir)
    digest = adapter_artifact_sha256(args.adapter_dir)
    if args.json:
        print(json.dumps(
            {"adapter_artifact_sha256": digest, "files": manifest},
            indent=2, sort_keys=True
        ))
    else:
        print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
