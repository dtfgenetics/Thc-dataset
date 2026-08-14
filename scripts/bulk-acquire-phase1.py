#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bulk_acquisition" / "phase1"
WORK = ROOT / "bulk_acquisition" / "work"
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

USER_AGENT = "THC-Plant-Diagnostic-Dataset/1.0 (+https://github.com/dtfgenetics/Thc-dataset)"


def run(args: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(args, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.stdout.strip()


def digest(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    with urllib.request.urlopen(req, timeout=180) as resp, tmp.open("wb") as out:
        while True:
            block = resp.read(1024 * 1024)
            if not block:
                break
            out.write(block)
        meta = {
            "finalUrl": resp.geturl(),
            "contentType": resp.headers.get("Content-Type"),
            "contentLengthHeader": resp.headers.get("Content-Length"),
        }
    tmp.replace(dest)
    meta["sizeBytes"] = dest.stat().st_size
    meta["sha256"] = digest(dest, "sha256")
    return meta


def write_inventory(rows: list[dict], path: Path) -> None:
    keys = [
        "datasetId", "relativePath", "sizeBytes", "sha256", "sourceGroupId",
        "sourceClass", "role", "trainingEligible", "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in keys})


def acquire_ds090() -> dict:
    ds = "DS-090"
    repo = "https://github.com/fearro/IoT_monitoring_hemp.git"
    commit = "86cec1c30494c23c1d9b724ceb1a3aec68709250"
    canonical = "https://data.mendeley.com/datasets/3md2tbx74c/1"
    work = WORK / "ds090_repo"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        run(["git", "init", "-q"], cwd=work)
        run(["git", "remote", "add", "origin", repo], cwd=work)
        run(["git", "fetch", "--depth", "1", "origin", commit], cwd=work)
        run(["git", "checkout", "-q", "FETCH_HEAD"], cwd=work)
        actual = run(["git", "rev-parse", "HEAD"], cwd=work)
        if actual != commit:
            raise RuntimeError(f"Pinned commit mismatch: expected {commit}, got {actual}")

        expected_trees = {
            "Hemp_growth/C1": "8b9cf5739d37651628b430083bc3dc44c2bac204",
            "Hemp_growth/C2": "ae68eadb3c159e4b11731538e688da6038f218ba",
            "Hemp_growth/C3": "9e0979570562594183a630baf4b63a16d578c4fc",
            "Hemp_growth/C4": "4138ad3c06eea92de68f41bff9f91388f8b66708",
            "Hemp_growth/C5": "c792399766afaec64cebd2336f61a1d2212491ca",
            "Hemp_water_stress/train": "decbeb56bc1a3b4b6ce64248b3e4805b7169ac29",
            "Hemp_water_stress/test": "0457eb36d8140bb958d29b5a71e23cad7897a7d5",
        }
        verified_trees = {}
        for rel, expected in expected_trees.items():
            actual_tree = run(["git", "rev-parse", f"HEAD:{rel}"], cwd=work)
            if actual_tree != expected:
                raise RuntimeError(f"Tree mismatch for {rel}: expected {expected}, got {actual_tree}")
            verified_trees[rel] = actual_tree

        files: list[Path] = []
        for base in [work / "Hemp_growth", work / "Hemp_water_stress"]:
            files.extend(sorted(p for p in base.rglob("*") if p.is_file()))

        jpgs = [p for p in files if p.suffix.lower() in {".jpg", ".jpeg"}]
        stress_jpgs = [p for p in jpgs if "Hemp_water_stress/train" in p.as_posix() or "Hemp_water_stress/test" in p.as_posix()]
        if len(stress_jpgs) != 378:
            raise RuntimeError(f"Expected 378 water-stress JPEGs, found {len(stress_jpgs)}")

        inventory = []
        growth_counts = {f"C{i}": 0 for i in range(1, 6)}
        stress_counts: dict[str, int] = {}
        for p in files:
            rel = p.relative_to(work).as_posix()
            group = ""
            source_class = ""
            role = "source-data"
            eligible = True
            notes = ""
            if rel.startswith("Hemp_growth/"):
                parts = rel.split("/")
                plant = parts[1] if len(parts) > 1 else "unknown"
                group = f"DS090-{plant}"
                growth_counts[plant] = growth_counts.get(plant, 0) + 1
                source_class = "temporal-growth"
                notes = "All frames from this plant/time-series must remain in one split."
            elif rel.startswith("Hemp_water_stress/train/") or rel.startswith("Hemp_water_stress/test/"):
                parts = rel.split("/")
                source_class = parts[2] if len(parts) > 2 else "unknown"
                stress_counts[source_class] = stress_counts.get(source_class, 0) + (1 if p.suffix.lower() in {".jpg", ".jpeg"} else 0)
                name = p.name
                plant = "unknown"
                if name.startswith("ryb_C") and len(name) >= 6:
                    plant = name.split("_")[1]
                group = f"DS090-{plant}"
                notes = "Published train/test assignment is source metadata only; regroup by plant/time-series before our split."
            if rel.endswith("yolo11x-cls.pt"):
                role = "published-model-reproducibility-only"
                eligible = False
                group = "DS090-PUBLISHED-MODEL"
                source_class = "model"
                notes = "Never use these weights or their outputs as ground-truth training/evaluation data."
            inventory.append({
                "datasetId": ds,
                "relativePath": rel,
                "sizeBytes": p.stat().st_size,
                "sha256": digest(p),
                "sourceGroupId": group,
                "sourceClass": source_class,
                "role": role,
                "trainingEligible": str(eligible).lower(),
                "notes": notes,
            })

        inv_path = OUT / "DS-090_file_inventory.csv"
        write_inventory(inventory, inv_path)
        archive = OUT / "DS-090_hemp-water-stress_pinned-86cec1c.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            for name in ["README.md", "Hemp_growth", "Hemp_water_stress"]:
                path = work / name
                if path.exists():
                    tf.add(path, arcname=name)

        model = work / "Hemp_water_stress" / "model" / "yolo11x-cls.pt"
        model_meta = None
        if model.exists():
            model_meta = {
                "sizeBytes": model.stat().st_size,
                "gitBlobSha1": run(["git", "hash-object", str(model)], cwd=work),
                "sha256": digest(model),
                "trainingEligible": False,
                "evaluationEligible": False,
            }

        return {
            "datasetId": ds,
            "status": "acquired",
            "canonicalRightsSource": canonical,
            "acquisitionSource": repo,
            "pinnedCommit": commit,
            "verifiedTrees": verified_trees,
            "fileCount": len(files),
            "jpegCount": len(jpgs),
            "waterStressJpegCount": len(stress_jpgs),
            "growthCounts": growth_counts,
            "stressClassCounts": stress_counts,
            "archive": archive.name,
            "archiveSizeBytes": archive.stat().st_size,
            "archiveSha256": digest(archive),
            "inventory": inv_path.name,
            "publishedModel": model_meta,
            "license": "CC BY 4.0 via canonical Mendeley Data record",
            "splitPolicy": "Merge source train/test, deduplicate, then group all frames/derivatives by plant/time-series before assigning our splits.",
        }
    except Exception as exc:
        return {"datasetId": ds, "status": "blocked", "error": str(exc), "canonicalRightsSource": canonical}


def acquire_ds071() -> dict:
    ds = "DS-071"
    dest = OUT / "DS-071_cannabis-nutrient-deficiency_supplement.zip"
    candidates = [
        "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9920212/supplementaryFiles",
        "https://mdpi-res.com/d_attachment/plants/plants-12-00422/article_deploy/plants-12-00422-s001.zip",
    ]
    errors = []
    for url in candidates:
        try:
            if dest.exists():
                dest.unlink()
            meta = download(url, dest)
            if not zipfile.is_zipfile(dest):
                raise RuntimeError(f"Response was not a ZIP ({meta.get('contentType')}, {dest.stat().st_size} bytes)")
            if dest.stat().st_size < 10_000_000:
                raise RuntimeError(f"ZIP unexpectedly small: {dest.stat().st_size} bytes")
            rows = []
            with zipfile.ZipFile(dest) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    rows.append({
                        "name": info.filename,
                        "compressedSize": info.compress_size,
                        "uncompressedSize": info.file_size,
                        "crc32": f"{info.CRC:08x}",
                    })
            inv = OUT / "DS-071_zip_inventory.json"
            inv.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            return {
                "datasetId": ds,
                "status": "acquired",
                "canonicalSource": "https://pmc.ncbi.nlm.nih.gov/articles/PMC9920212/",
                "doi": "10.3390/plants12030422",
                "downloadRoute": url,
                "finalUrl": meta["finalUrl"],
                "archive": dest.name,
                "archiveSizeBytes": dest.stat().st_size,
                "archiveSha256": digest(dest),
                "zipEntryCount": len(rows),
                "inventory": inv.name,
                "license": "CC BY 4.0",
                "useRule": "Preserve treatment, week, organ and figure identity. Visual appearance supports a differential but does not replace root-zone pH/EC/feed/history/tissue context.",
            }
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    if dest.exists():
        dest.unlink()
    return {"datasetId": ds, "status": "blocked", "error": " | ".join(errors)}


def acquire_ds165() -> dict:
    ds = "DS-165"
    dest = OUT / "DS-165_Polyphagotarsonemus_latus_USDA_BARC.jpg"
    url = "https://commons.wikimedia.org/wiki/Special:Redirect/file/Polyphagotarsonemus%20latus%2C%20USDA%20BARC.jpg"
    expected_size = 1_845_677
    expected_sha1 = "0c7adac292bdd1d0c31df51d13635e872b311a42"
    try:
        meta = download(url, dest)
        actual_size = dest.stat().st_size
        actual_sha1 = digest(dest, "sha1")
        if actual_size != expected_size:
            raise RuntimeError(f"Size mismatch: expected {expected_size}, got {actual_size}")
        if actual_sha1 != expected_sha1:
            raise RuntimeError(f"SHA-1 mismatch: expected {expected_sha1}, got {actual_sha1}")
        return {
            "datasetId": ds,
            "status": "acquired",
            "source": "Wikimedia Commons mirror of USDA ARS micrograph",
            "downloadRoute": url,
            "finalUrl": meta["finalUrl"],
            "file": dest.name,
            "sizeBytes": actual_size,
            "providerSha1": actual_sha1,
            "sha256": digest(dest),
            "dimensions": "2894x2480",
            "license": "Public domain — USDA Agricultural Research Service",
            "useRule": "Organism morphology transfer/reference only; not Cannabis-host feeding-damage ground truth.",
        }
    except Exception as exc:
        if dest.exists():
            dest.unlink()
        return {"datasetId": ds, "status": "blocked", "error": str(exc)}


def main() -> int:
    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    results = [acquire_ds090(), acquire_ds071(), acquire_ds165()]
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schemaVersion": "1.0",
        "phase": "bulk-acquisition-phase1",
        "createdAt": now,
        "repository": "dtfgenetics/Thc-dataset",
        "results": results,
        "truthRule": "Only records with status=acquired have bytes present in this release bundle. Metadata-only or failed downloads remain blocked.",
    }
    manifest_path = OUT / "phase1-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary_lines = [
        "# THC Plant Diagnostic — Bulk Acquisition Phase 1",
        "",
        f"Generated: {now}",
        "",
    ]
    for r in results:
        summary_lines.append(f"- **{r['datasetId']}** — `{r['status']}`" + (f" — {r.get('error')}" if r['status'] != 'acquired' else ""))
    summary_lines += [
        "",
        "## Guardrails",
        "",
        "- Cross-crop or organism-reference assets do not become Cannabis causal ground truth by acquisition.",
        "- DS-090 source train/test folders are not reused as our benchmark split; regroup by plant/time-series first.",
        "- The DS-090 published classifier is retained only for reproducibility and is excluded from our training/evaluation pools.",
        "- DS-071 symptom progression remains context-dependent and should be combined with root-zone/feed/tissue evidence.",
        "",
    ]
    (OUT / "phase1-summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    checksum_lines = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "phase1-checksums.sha256":
            checksum_lines.append(f"{digest(p)}  {p.name}")
    (OUT / "phase1-checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    acquired = [r for r in results if r["status"] == "acquired"]
    print(json.dumps(manifest, indent=2))
    print(f"Acquired {len(acquired)}/{len(results)} phase-1 datasets")
    return 0 if acquired else 1


if __name__ == "__main__":
    raise SystemExit(main())
