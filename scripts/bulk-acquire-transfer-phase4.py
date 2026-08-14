#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bulk_acquisition" / "phase4_transfer"
WORK = ROOT / "bulk_acquisition" / "work_phase4_transfer"
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

USER_AGENT = "THC-Plant-Diagnostic-Dataset/1.0 (+https://github.com/dtfgenetics/Thc-dataset)"
CHUNK_BYTES = 95_000_000

DATASETS = [
    {
        "datasetId": "DS-142",
        "mendeleyId": "jwc8k4997r",
        "version": 1,
        "title": "TeaLeaf-4",
        "expectedImageCount": 3156,
        "license": "CC BY 4.0",
        "role": "cross-crop transfer: red-spider/skeletonization/sun-scorch/healthy; white-background domain shift",
    },
    {
        "datasetId": "DS-143",
        "mendeleyId": "zg93th7mhb",
        "version": 1,
        "title": "MangoLeafDiseasesDataset",
        "expectedImageCount": 3000,
        "license": "CC BY 4.0",
        "role": "cross-crop transfer: scale insects/sooty mold/dieback/healthy; retain text annotations",
    },
    {
        "datasetId": "DS-144",
        "mendeleyId": "ss63ftnjnh",
        "version": 5,
        "title": "High-Resolution Eggplant Leaf Image Dataset v5",
        "expectedImageCount": 1338,
        "license": "CC BY 4.0",
        "role": "cross-crop high-resolution field transfer; retain metadata.csv and original filenames",
    },
    {
        "datasetId": "DS-146",
        "mendeleyId": "wkjg6srrk8",
        "version": 1,
        "title": "CottonPest-BD",
        "expectedImageCount": 1625,
        "license": "CC BY 4.0",
        "role": "beneficial/non-pest arthropod hard negatives plus pest discrimination transfer",
    },
]


def digest(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def request(url: str, accept: str | None = None):
    headers = {"User-Agent": USER_AGENT, "Accept": accept or "*/*"}
    return urllib.request.Request(url, headers=headers)


def fetch_json(url: str, accept: str = "application/vnd.mendeley-public-dataset.1+json") -> dict:
    with urllib.request.urlopen(request(url, accept), timeout=120) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8"))


def download(url: str, dest: Path) -> dict:
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.unlink(missing_ok=True)
    req = request(url)
    with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as out:
        while True:
            block = resp.read(4 * 1024 * 1024)
            if not block:
                break
            out.write(block)
        meta = {
            "requestedUrl": url,
            "finalUrl": resp.geturl(),
            "contentType": resp.headers.get("Content-Type"),
            "contentLengthHeader": resp.headers.get("Content-Length"),
        }
    tmp.replace(dest)
    meta["sizeBytes"] = dest.stat().st_size
    meta["sha256"] = digest(dest)
    return meta


def metadata_routes(mid: str, version: int) -> list[str]:
    encoded = urllib.parse.urlencode({"version": version, "fields": "*"})
    return [
        f"https://api.data.mendeley.com/datasets/{mid}?{encoded}",
        f"https://api.mendeley.com/datasets/{mid}?{encoded}",
    ]


def zip_routes(mid: str, version: int) -> list[str]:
    return [
        f"https://api.data.mendeley.com/datasets/{mid}/zip/file_downloaded?version={version}",
        f"https://api.mendeley.com/datasets/{mid}/zip/file_downloaded?version={version}",
    ]


def page_fallback_routes(mid: str, version: int) -> list[str]:
    return [
        f"https://data.mendeley.com/public-files/datasets/{mid}/files?version={version}",
        f"https://data.mendeley.com/datasets/{mid}/{version}",
    ]


def resolve_metadata(mid: str, version: int) -> tuple[dict | None, list[str]]:
    errors = []
    for url in metadata_routes(mid, version):
        try:
            data = fetch_json(url)
            if isinstance(data, dict):
                return data, errors
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    return None, errors


def extract_file_rows(metadata: dict | None) -> list[dict]:
    if not metadata:
        return []
    files = metadata.get("files") or []
    rows = []
    for item in files:
        if not isinstance(item, dict):
            continue
        cd = item.get("content_details") or {}
        rows.append({
            "id": item.get("id") or cd.get("id"),
            "filename": item.get("filename"),
            "size": item.get("size") or cd.get("size"),
            "sha256_hash": cd.get("sha256_hash"),
            "download_url": cd.get("download_url"),
            "content_type": cd.get("content_type"),
            "folder_id": item.get("folder_id"),
        })
    return rows


def try_zip_download(mid: str, version: int, dest: Path) -> tuple[dict | None, list[str]]:
    errors = []
    for url in zip_routes(mid, version):
        try:
            meta = download(url, dest)
            if dest.stat().st_size < 1024:
                raise RuntimeError(f"download too small ({dest.stat().st_size} bytes)")
            if not zipfile.is_zipfile(dest):
                raise RuntimeError(f"response is not ZIP: type={meta.get('contentType')} size={dest.stat().st_size}")
            return meta, errors
        except Exception as exc:
            dest.unlink(missing_ok=True)
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    return None, errors


def try_individual_downloads(files: list[dict], dest_zip: Path) -> tuple[dict | None, list[str]]:
    errors = []
    usable = [f for f in files if f.get("download_url") and f.get("filename")]
    if not usable:
        return None, ["metadata contained no directly downloadable file URLs"]
    tmpdir = WORK / (dest_zip.stem + "_files")
    shutil.rmtree(tmpdir, ignore_errors=True)
    tmpdir.mkdir(parents=True)
    provider_checks = []
    try:
        for idx, item in enumerate(usable, start=1):
            raw_name = str(item["filename"])
            safe = Path(raw_name).name
            target = tmpdir / f"{idx:04d}_{safe}"
            meta = download(str(item["download_url"]), target)
            if item.get("sha256_hash"):
                expected = str(item["sha256_hash"]).lower()
                actual = meta["sha256"].lower()
                if expected != actual:
                    raise RuntimeError(f"provider SHA256 mismatch for {raw_name}: expected {expected}, got {actual}")
            provider_checks.append({
                "filename": raw_name,
                "localFilename": target.name,
                "sizeBytes": target.stat().st_size,
                "sha256": meta["sha256"],
                "providerSha256": item.get("sha256_hash"),
            })
        with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for p in sorted(tmpdir.iterdir()):
                zf.write(p, arcname=p.name)
        return {
            "requestedUrl": "metadata.content_details.download_url",
            "finalUrl": "multiple",
            "contentType": "application/zip",
            "sizeBytes": dest_zip.stat().st_size,
            "sha256": digest(dest_zip),
            "providerFileChecks": provider_checks,
        }, errors
    except Exception as exc:
        dest_zip.unlink(missing_ok=True)
        errors.append(f"individual files: {type(exc).__name__}: {exc}")
        return None, errors


def inspect_zip(path: Path) -> dict:
    image_ext = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    annotation_ext = {".txt", ".csv", ".json", ".xml", ".yaml", ".yml"}
    rows = []
    images = 0
    annotations = 0
    total_uncompressed = 0
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            suffix = Path(info.filename).suffix.lower()
            if suffix in image_ext:
                images += 1
            if suffix in annotation_ext:
                annotations += 1
            total_uncompressed += info.file_size
            rows.append({
                "name": info.filename,
                "compressedSize": info.compress_size,
                "uncompressedSize": info.file_size,
                "crc32": f"{info.CRC:08x}",
                "isImage": suffix in image_ext,
                "isAnnotation": suffix in annotation_ext,
            })
    return {
        "entryCount": len(rows),
        "imageEntryCount": images,
        "annotationEntryCount": annotations,
        "uncompressedBytes": total_uncompressed,
        "entries": rows,
    }


def chunk_file(path: Path, dataset_id: str) -> list[dict]:
    if path.stat().st_size <= CHUNK_BYTES:
        return [{
            "filename": path.name,
            "sizeBytes": path.stat().st_size,
            "sha256": digest(path),
            "partIndex": 1,
            "partCount": 1,
            "reconstruct": "use file directly",
        }]
    parts = []
    with path.open("rb") as src:
        idx = 1
        while True:
            data = src.read(CHUNK_BYTES)
            if not data:
                break
            part = OUT / f"{dataset_id}_archive.part{idx:03d}"
            part.write_bytes(data)
            parts.append({
                "filename": part.name,
                "sizeBytes": part.stat().st_size,
                "sha256": digest(part),
                "partIndex": idx,
                "reconstruct": f"concatenate parts in numeric order to reconstruct {path.name}",
            })
            idx += 1
    for p in parts:
        p["partCount"] = len(parts)
    # Keep original ZIP only in the workflow workspace when chunked; release/upload uses parts.
    path.unlink()
    return parts


def acquire(ds: dict) -> dict:
    did = ds["datasetId"]
    mid = ds["mendeleyId"]
    version = ds["version"]
    archive = OUT / f"{did}_{mid}_v{version}.zip"

    metadata, meta_errors = resolve_metadata(mid, version)
    file_rows = extract_file_rows(metadata)
    if metadata:
        (OUT / f"{did}_provider_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (OUT / f"{did}_provider_file_manifest.json").write_text(json.dumps(file_rows, indent=2), encoding="utf-8")

    dl_meta, zip_errors = try_zip_download(mid, version, archive)
    individual_errors = []
    route = "mendeley_zip_endpoint"
    if dl_meta is None:
        dl_meta, individual_errors = try_individual_downloads(file_rows, archive)
        route = "provider_file_urls"

    if dl_meta is None:
        return {
            **ds,
            "status": "blocked",
            "metadataResolved": bool(metadata),
            "providerFileCount": len(file_rows),
            "errors": meta_errors + zip_errors + individual_errors,
            "truthRule": "No acquisition status without verified local bytes.",
        }

    zinfo = inspect_zip(archive)
    inv_path = OUT / f"{did}_zip_inventory.json"
    inv_path.write_text(json.dumps(zinfo, indent=2), encoding="utf-8")
    original_size = archive.stat().st_size
    original_sha = digest(archive)
    parts = chunk_file(archive, did)
    chunks_path = OUT / f"{did}_archive_parts.json"
    chunks_path.write_text(json.dumps(parts, indent=2), encoding="utf-8")

    count_match = zinfo["imageEntryCount"] == ds["expectedImageCount"]
    return {
        **ds,
        "status": "acquired",
        "downloadRoute": route,
        "metadataResolved": bool(metadata),
        "providerFileCount": len(file_rows),
        "archiveSizeBytes": original_size,
        "archiveSha256": original_sha,
        "zipEntryCount": zinfo["entryCount"],
        "imageEntryCount": zinfo["imageEntryCount"],
        "annotationEntryCount": zinfo["annotationEntryCount"],
        "expectedImageCountMatch": count_match,
        "archiveParts": parts,
        "providerDownloadMeta": dl_meta,
        "guardrail": "Cross-crop labels remain transfer-only and cannot become Cannabis causal ground truth. Raw source classes and host context must be preserved.",
    }


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.rmtree(WORK, ignore_errors=True)
    OUT.mkdir(parents=True)
    WORK.mkdir(parents=True)

    results = [acquire(ds) for ds in DATASETS]
    created = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schemaVersion": "1.0",
        "phase": "bulk-acquisition-transfer-phase4",
        "createdAt": created,
        "repository": "dtfgenetics/Thc-dataset",
        "chunkBytes": CHUNK_BYTES,
        "results": results,
        "truthRule": "Only status=acquired has verified bytes in the workflow output. Cross-crop acquisition does not promote causal labels to Cannabis ground truth.",
    }
    (OUT / "phase4-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = ["# THC Plant Diagnostic — Bulk Transfer Acquisition Phase 4", "", f"Generated: {created}", ""]
    for r in results:
        if r["status"] == "acquired":
            lines.append(f"- **{r['datasetId']} {r['title']}** — acquired — {r['imageEntryCount']} image entries — {r['archiveSizeBytes']:,} bytes")
        else:
            lines.append(f"- **{r['datasetId']} {r['title']}** — blocked — metadataResolved={r.get('metadataResolved')} — providerFiles={r.get('providerFileCount')}")
    lines += ["", "## Safety and data-integrity rules", "", "- All four sources remain cross-crop transfer data.", "- Preserve original host and source labels before any ontology mapping.", "- Do not treat patch/derived copies or archive mirrors as independent biological samples.", "- Training eligibility still requires per-file hashing/pHash, duplicate review, and source-group/split review."]
    (OUT / "phase4-summary.md").write_text("\n".join(lines), encoding="utf-8")

    checks = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "phase4-checksums.sha256":
            checks.append(f"{digest(p)}  {p.name}")
    (OUT / "phase4-checksums.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")
    print(json.dumps({"phase": manifest["phase"], "results": [{"datasetId": r["datasetId"], "status": r["status"], "imageEntryCount": r.get("imageEntryCount"), "archiveSizeBytes": r.get("archiveSizeBytes")} for r in results]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
