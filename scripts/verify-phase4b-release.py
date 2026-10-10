#!/usr/bin/env python3
"""Verify persistent Phase 4B release assets against a local acquisition manifest.

This verifies transport integrity, NOT image labels, training rights or diagnoses.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

EXPECTED = {"DS-142", "DS-143", "DS-146"}

def gh_json(*args: str):
    p = subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True)
    return json.loads(p.stdout)

def validate(manifest: dict, assets: list[dict], root: Path) -> dict:
    errors = []
    if root.is_symlink():
        return {"status": "fail", "verifiedParts": 0, "declaredParts": 0, "errors": ["Archive root must not be a symlink"]}
    if not root.is_dir():
        return {"status": "fail", "verifiedParts": 0, "declaredParts": 0, "errors": ["Archive root must be an existing directory"]}
    if not isinstance(manifest, dict):
        return {"status": "fail", "verifiedParts": 0, "declaredParts": 0, "errors": ["Manifest must be an object"]}
    rows = manifest.get("results", [])
    if not isinstance(rows, list) or len(rows) != 3 or any(not isinstance(r, dict) or not isinstance(r.get("datasetId"), str) for r in rows) or {r["datasetId"] for r in rows} != EXPECTED:
        errors.append("Expected exactly DS-142, DS-143 and DS-146")
        rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    by_name = {}
    if not isinstance(assets, list):
        return {"status": "fail", "verifiedParts": 0, "declaredParts": 0, "errors": ["Release assets must be a list"]}
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("name"), str):
            errors.append("Malformed release asset entry")
            continue
        name = asset.get("name")
        if name in by_name:
            errors.append(f"Duplicate release asset {name}")
        by_name[name] = asset
    declared = set()
    audited = 0
    for row in rows:
        did = row.get("datasetId", "?")
        if not isinstance(did, str):
            errors.append("Malformed dataset ID")
            continue
        if row.get("status") != "acquired":
            errors.append(f"{did}: acquisition not successful")
        parts = row.get("archiveParts", [])
        if not isinstance(parts, list) or not parts:
            errors.append(f"{did}: no archive parts")
            continue
        indices = []
        original = row.get("originalArchive")
        if not isinstance(original, dict) or type(original.get("sizeBytes")) is not int or original["sizeBytes"] <= 0 or not isinstance(original.get("sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", original["sha256"]) is None:
            errors.append(f"{did}: invalid original archive metadata")
        archive_digest = hashlib.sha256()
        archive_size = 0
        # Reconstruct in numeric chunk order, regardless of manifest row ordering.
        for part in sorted(parts, key=lambda item: item.get("filename", "") if isinstance(item, dict) and isinstance(item.get("filename"), str) else ""):
            if not isinstance(part, dict):
                errors.append(f"{did}: malformed archive part")
                continue
            if type(part.get("sizeBytes")) is not int or part["sizeBytes"] <= 0:
                errors.append(f"{did}: invalid non-positive archive part size")
                continue
            name = part.get("filename", "")
            if not isinstance(name, str) or re.fullmatch(re.escape(f"{did}_archive.part") + r"[0-9]{3}", name) is None:
                errors.append(f"{did}: invalid filename {name!r}")
                continue
            if not isinstance(part.get("sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", part["sha256"]) is None:
                errors.append(f"{did}: invalid archive part SHA256: {name}")
                continue
            indices.append(int(name[-3:]))
            if name in declared:
                errors.append(f"Duplicate declared part {name}")
            declared.add(name)
            local = root / name
            if local.is_symlink():
                errors.append(f"Symlink archive part rejected: {name}")
                continue
            if not local.is_file():
                errors.append(f"Missing local part {name}")
                continue
            part_digest = hashlib.sha256()
            with local.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    part_digest.update(block)
                    archive_digest.update(block)
                    archive_size += len(block)
            checksum = part_digest.hexdigest()
            if checksum != part.get("sha256") or local.stat().st_size != part.get("sizeBytes"):
                errors.append(f"Local checksum/size differs from manifest: {name}")
                continue
            asset = by_name.get(name)
            if not asset:
                errors.append(f"Missing release asset: {name}")
                continue
            if asset.get("state") != "uploaded":
                errors.append(f"Release asset is not uploaded: {name}")
                continue
            if type(asset.get("size")) is not int or asset["size"] <= 0 or asset["size"] != part["sizeBytes"]:
                errors.append(f"Release asset size mismatch: {name}")
                continue
            digest = asset.get("digest")
            if not isinstance(digest, str) or not digest.startswith("sha256:"):
                errors.append(f"Release asset lacks verifiable SHA256 digest: {name}")
                continue
            if digest != f"sha256:{checksum}":
                errors.append(f"Release digest mismatch: {name}")
                continue
            audited += 1
        if isinstance(original, dict) and (archive_size != original.get("sizeBytes") or archive_digest.hexdigest() != original.get("sha256")):
            errors.append(f"{did}: reconstructed archive checksum/size mismatch")
        if sorted(indices) != list(range(1, len(indices) + 1)):
            errors.append(f"{did}: part sequence has gaps or duplicates")
    unexpected = sorted(name for name in by_name if any(name.startswith(f"{did}_archive.part") for did in EXPECTED) and name not in declared)
    undeclared_local = sorted(path.name for path in root.iterdir() if (path.is_file() or path.is_symlink()) and any(path.name.startswith(f"{did}_archive.part") for did in EXPECTED) and path.name not in declared)
    if undeclared_local:
        errors.append(f"Undeclared local archive parts: {', '.join(undeclared_local)}")
    if unexpected:
        errors.append(f"Undeclared release archive assets: {', '.join(unexpected)}")
    return {"status": "pass" if not errors else "fail", "verifiedParts": audited,
            "declaredParts": len(declared), "errors": errors}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args()
    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY required")
    try:
        manifest = json.loads(args.manifest.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "verifiedParts": 0, "declaredParts": 0,
                          "errors": [f"Cannot load acquisition manifest: {exc}"]}, indent=2))
        return 1
    try:
        release = gh_json(f"repos/{args.repo}/releases/tags/{args.tag}")
        release_id = release["id"]
        assets = []
        page = 1
        while True:
            batch = gh_json(f"repos/{args.repo}/releases/{release_id}/assets?per_page=100&page={page}")
            if not isinstance(batch, list):
                raise ValueError("Release asset response must be a list")
            assets.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "verifiedParts": 0, "declaredParts": 0,
                          "errors": [f"Cannot load release assets: {exc}"]}, indent=2))
        return 1
    report = validate(manifest, assets, args.root)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1

if __name__ == "__main__":
    sys.exit(main())
