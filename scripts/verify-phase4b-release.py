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
        for part in parts:
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
            indices.append(int(name[-3:]))
            if name in declared:
                errors.append(f"Duplicate declared part {name}")
            declared.add(name)
            local = root / name
            if not local.is_file():
                errors.append(f"Missing local part {name}")
                continue
            with local.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
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
            if asset.get("size") != part.get("sizeBytes"):
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
        if sorted(indices) != list(range(1, len(indices) + 1)):
            errors.append(f"{did}: part sequence has gaps or duplicates")
    unexpected = sorted(name for name in by_name if any(name.startswith(f"{did}_archive.part") for did in EXPECTED) and name not in declared)
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
    manifest = json.loads(args.manifest.read_text())
    release = gh_json(f"repos/{args.repo}/releases/tags/{args.tag}")
    release_id = release["id"]
    assets = []
    page = 1
    while True:
        batch = gh_json(f"repos/{args.repo}/releases/{release_id}/assets?per_page=100&page={page}")
        assets.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    report = validate(manifest, assets, args.root)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1

if __name__ == "__main__":
    sys.exit(main())
