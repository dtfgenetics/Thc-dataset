#!/usr/bin/env python3
"""Audit Phase 4B GitHub release *metadata*; never infer byte integrity or image rights."""
import argparse
import json
import re
from pathlib import Path

DATASETS = {"DS-142", "DS-143", "DS-146"}
PART = re.compile(r"^(DS-\d+)_archive\.part(\d{3})$")


def audit(manifest, assets):
    errors = []
    if not isinstance(manifest, dict) or not isinstance(manifest.get("results"), list):
        return {"status": "fail", "scope": "metadata-only", "errors": ["Invalid manifest"]}
    if not isinstance(assets, list):
        return {"status": "fail", "scope": "metadata-only", "errors": ["Invalid assets"]}
    expected = {}
    seen_datasets = set()
    for row in manifest["results"]:
        if not isinstance(row, dict) or row.get("datasetId") not in DATASETS:
            errors.append("Unexpected manifest dataset")
            continue
        did = row["datasetId"]
        if did in seen_datasets:
            errors.append("Duplicate manifest dataset: " + did)
        seen_datasets.add(did)
        parts = row.get("parts")
        if not isinstance(parts, list):
            errors.append("Missing parts for " + did)
            continue
        for part in parts:
            if not isinstance(part, dict) or not isinstance(part.get("name"), str):
                errors.append("Malformed part for " + did)
                continue
            name = part["name"]
            match = PART.fullmatch(name)
            if not match or match.group(1) != did or name in expected:
                errors.append("Invalid or duplicate part: " + name)
            else:
                expected[name] = part
    if seen_datasets != DATASETS:
        errors.append("Manifest dataset coverage incomplete")
    published = {}
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("name"), str):
            errors.append("Malformed release asset")
            continue
        name = asset["name"]
        if PART.fullmatch(name):
            if name in published:
                errors.append("Duplicate published part: " + name)
            published[name] = asset
    for name, part in expected.items():
        asset = published.get(name)
        if asset is None:
            errors.append("Missing published part: " + name)
            continue
        if type(part.get("size")) is int and asset.get("size") != part["size"]:
            errors.append("Size mismatch: " + name)
        digest = part.get("sha256")
        if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
            if asset.get("digest") != "sha256:" + digest:
                errors.append("Digest metadata mismatch: " + name)
        else:
            errors.append("Invalid manifest SHA-256: " + name)
    for name in published.keys() - expected.keys():
        errors.append("Undeclared published part: " + name)
    return {"status": "fail" if errors else "pass", "scope": "metadata-only",
            "expectedParts": len(expected), "publishedParts": len(published), "errors": errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(json.loads(args.manifest.read_text()), json.loads(args.assets.read_text()))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        report = {"status": "fail", "scope": "metadata-only", "errors": [str(exc)]}
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
