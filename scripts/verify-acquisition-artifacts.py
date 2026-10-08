#!/usr/bin/env python3
"""Validate acquired dataset tar shards against their packaging manifest."""
from __future__ import annotations
import argparse
import hashlib
import json
import tarfile
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def verify(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for field in ("datasetId", "sourceUrl", "sourceRevision", "license"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            errors.append(f"Missing provenance field: {field}")
    shards = manifest.get("shards", [])
    if not isinstance(shards, list) or not shards:
        errors.append("No shards in manifest")
        shards = []
    seen = set()
    total_files = total_images = total_bytes = 0
    for shard in shards:
        name = shard.get("fileName", "")
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".tar"):
            errors.append(f"Unsafe shard filename: {name!r}")
            continue
        if name in seen:
            errors.append(f"Duplicate shard: {name}")
            continue
        seen.add(name)
        archive_path = path.parent / name
        if not archive_path.is_file():
            errors.append(f"Missing shard: {name}")
            continue
        size = archive_path.stat().st_size
        total_bytes += size
        if size != shard.get("bytes"):
            errors.append(f"Byte mismatch: {name}")
        if sha256(archive_path) != shard.get("sha256"):
            errors.append(f"SHA256 mismatch: {name}")
        try:
            with tarfile.open(archive_path, "r:") as archive:
                members = archive.getmembers()
                if any(m.issym() or m.islnk() or m.isdev() or m.isfifo() or
                       m.name.startswith("/") or ".." in Path(m.name).parts for m in members):
                    errors.append(f"Unsafe archive member: {name}")
                paths = [m.name for m in members]
                if len(paths) != len(set(paths)):
                    errors.append(f"Duplicate archive member path: {name}")
                if any(not (m.isfile() or m.isdir()) for m in members):
                    errors.append(f"Unsupported archive member type: {name}")
                count = sum(m.isfile() for m in members)
                images = sum(m.isfile() and Path(m.name).suffix.lower() in IMAGE_EXTS for m in members)
                total_files += count
                total_images += images
                if count != shard.get("fileCount") or images != shard.get("imageCount"):
                    errors.append(f"File/image count mismatch: {name}")
        except (OSError, tarfile.TarError) as exc:
            errors.append(f"Unreadable tar {name}: {exc}")
    for field, actual in (("shardCount", len(shards)), ("totalFiles", total_files),
                          ("totalImages", total_images), ("totalArchiveBytes", total_bytes)):
        if manifest.get(field) != actual:
            errors.append(f"{field} mismatch: expected={manifest.get(field)} actual={actual}")
    if total_images == 0:
        errors.append("No images packaged")
    return {"datasetId": manifest.get("datasetId"), "manifest": str(path),
            "images": total_images, "status": "pass" if not errors else "fail", "errors": errors}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="+", type=Path)
    manifests = parser.parse_args().manifests
    results = [verify(p) for p in manifests]
    # Multiple manifests may share one directory (train/test or growth/stress).
    by_directory = {}
    for path, result in zip(manifests, results):
        directory = path.parent.resolve()
        entry = by_directory.setdefault(directory, {"declared": set(), "results": []})
        entry["results"].append(result)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entry["declared"].update(
                shard.get("fileName") for shard in data.get("shards", [])
                if isinstance(shard, dict) and isinstance(shard.get("fileName"), str)
            )
        except (OSError, ValueError, TypeError):
            result["errors"].append("Unreadable manifest")
            result["status"] = "fail"
    for directory, item in by_directory.items():
        unlisted = sorted(p.name for p in directory.glob("*.tar")
                          if p.name not in item["declared"])
        if unlisted:
            for result in item["results"]:
                result["errors"].append(f"Unlisted tar shards: {unlisted}")
                result["status"] = "fail"
    print(json.dumps({"results": results}, indent=2))
    return int(any(result["status"] != "pass" for result in results))

if __name__ == "__main__":
    raise SystemExit(main())
