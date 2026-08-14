#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTROOT = ROOT / 'bulk_acquisition' / 'phase6_transfer'
WORKROOT = ROOT / 'bulk_acquisition' / 'work_phase6_transfer'
CHUNK_BYTES = 90_000_000
UA = 'THC-Plant-Diagnostic-Dataset/1.0 (+https://github.com/dtfgenetics/Thc-dataset)'
IMG_EXT = {'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}
ANN_EXT = {'.txt','.csv','.json','.xml','.yaml','.yml'}

DATASETS = {
    'DS-137': {
        'mendeleyId':'w9drvtxg9g','version':1,'title':'Pepper Bell Leaf Disease 2026','expectedImages':9283,'license':'CC BY 4.0',
        'role':'cross-crop transfer only: spot/curl/nutrition-deficiency/powdery-mildew/healthy patterns'
    },
    'DS-138': {
        'mendeleyId':'tm3v4zmh7c','version':1,'title':'Chilli Leaf Disease Image Dataset 2025','expectedImages':8814,'license':'CC BY 4.0',
        'role':'cross-crop real-phone transfer only: bacterial/Cercospora/curl-virus/nutrition-deficiency/powdery-mildew/healthy'
    },
    'DS-139': {
        'mendeleyId':'8d9fv6kpt3','version':2,'title':'Large-Scale Lemon Leaf Disease and Pest Image Dataset','expectedImages':17609,'license':'CC BY 4.0',
        'role':'cross-crop messy-phone transfer only: mite/leafminer/herbivory/sooty-mold/healthy and other source classes'
    },
    'DS-145': {
        'mendeleyId':'nnv3k3m94k','version':1,'title':'Pisum sativum Healthy and Disease-Affected Image Dataset','expectedImages':12096,'license':'CC BY 4.0',
        'role':'cross-crop transfer only: Botrytis/Fusarium/powdery-mildew/healthy and other pea-specific labels; preserve severe class imbalance'
    },
}


def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def download(url: str, dest: Path) -> dict:
    tmp = dest.with_suffix(dest.suffix + '.part')
    tmp.unlink(missing_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
    with urllib.request.urlopen(req, timeout=1800) as r, tmp.open('wb') as w:
        while True:
            b = r.read(4 * 1024 * 1024)
            if not b:
                break
            w.write(b)
        meta = {
            'requestedUrl': url,
            'finalUrl': r.geturl(),
            'contentType': r.headers.get('Content-Type'),
            'contentLengthHeader': r.headers.get('Content-Length'),
        }
    tmp.replace(dest)
    meta['sizeBytes'] = dest.stat().st_size
    meta['sha256'] = digest(dest)
    return meta


def inspect_zip(path: Path) -> dict:
    rows = []
    images = annotations = 0
    nested = []
    total_uncompressed = 0
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            suffix = Path(info.filename).suffix.lower()
            images += int(suffix in IMG_EXT)
            annotations += int(suffix in ANN_EXT)
            if suffix == '.zip':
                nested.append(info.filename)
            total_uncompressed += info.file_size
            rows.append({
                'name': info.filename,
                'compressedSize': info.compress_size,
                'uncompressedSize': info.file_size,
                'crc32': f'{info.CRC:08x}',
                'isImage': suffix in IMG_EXT,
                'isAnnotation': suffix in ANN_EXT,
            })
    return {
        'entryCount': len(rows),
        'directImageEntryCount': images,
        'annotationEntryCount': annotations,
        'nestedZipEntries': nested,
        'uncompressedBytes': total_uncompressed,
        'entries': rows,
    }


def chunk(path: Path, out: Path, did: str) -> list[dict]:
    parts = []
    with path.open('rb') as src:
        idx = 1
        while True:
            b = src.read(CHUNK_BYTES)
            if not b:
                break
            p = out / f'{did}_archive.part{idx:03d}'
            p.write_bytes(b)
            parts.append({'filename':p.name,'partIndex':idx,'sizeBytes':p.stat().st_size,'sha256':digest(p)})
            idx += 1
    for x in parts:
        x['partCount'] = len(parts)
        x['reconstruct'] = f'concatenate {did}_archive.partNNN in numeric order'
    return parts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('dataset_id', choices=sorted(DATASETS))
    args = ap.parse_args()
    did = args.dataset_id
    ds = DATASETS[did]
    out = OUTROOT / did
    work = WORKROOT / did
    shutil.rmtree(out, ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    out.mkdir(parents=True)
    work.mkdir(parents=True)

    url = f"https://data.mendeley.com/public-api/zip/{ds['mendeleyId']}/download/{ds['version']}"
    archive = work / f"{did}_{ds['mendeleyId']}_v{ds['version']}.zip"
    try:
        dl = download(url, archive)
        if not zipfile.is_zipfile(archive):
            raise RuntimeError(f"Download-All response is not ZIP: {dl.get('contentType')} {archive.stat().st_size} bytes")
        zi = inspect_zip(archive)
        original = {'filename':archive.name,'sizeBytes':archive.stat().st_size,'sha256':digest(archive)}
        parts = chunk(archive, out, did)
        (out / f'{did}_zip_inventory.json').write_text(json.dumps(zi, indent=2), encoding='utf-8')
        (out / f'{did}_archive_parts.json').write_text(json.dumps(parts, indent=2), encoding='utf-8')
        status = {
            'schemaVersion':'1.0','phase':'bulk-transfer-phase6','createdAt':datetime.now(timezone.utc).isoformat(),
            'datasetId':did, **ds, 'status':'acquired', 'downloadRoute':url, 'downloadMeta':dl,
            'originalArchive':original,'archiveParts':parts,'zipEntryCount':zi['entryCount'],
            'directImageEntryCount':zi['directImageEntryCount'],'annotationEntryCount':zi['annotationEntryCount'],
            'nestedZipEntries':zi['nestedZipEntries'],
            'expectedDirectImageCountMatch':zi['directImageEntryCount'] == ds['expectedImages'],
            'trainingGate':'HOLD: raw acquisition is not training eligibility. Extract nested packages where present, compute per-image SHA256/pHash, preserve host/classes, deduplicate, and assign leakage-safe splits. Cross-crop causal labels remain transfer-only.'
        }
    except Exception as exc:
        status = {'schemaVersion':'1.0','phase':'bulk-transfer-phase6','createdAt':datetime.now(timezone.utc).isoformat(),'datasetId':did,**ds,'status':'blocked','downloadRoute':url,'error':f'{type(exc).__name__}: {exc}','truthRule':'No acquired state without verified Download-All ZIP bytes.'}

    (out / f'{did}_phase6_manifest.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    summary = [f'# Phase 6 — {did} {ds["title"]}', '', f"Status: **{status['status']}**"]
    if status['status'] == 'acquired':
        summary += [f"Original archive: **{status['originalArchive']['sizeBytes']:,} bytes**", f"SHA-256: `{status['originalArchive']['sha256']}`", f"Bridge parts: **{len(status['archiveParts'])}**", f"Direct image entries: **{status['directImageEntryCount']}**", f"Nested ZIPs: **{len(status['nestedZipEntries'])}**"]
    else:
        summary += [status['error']]
    summary += ['', 'Cross-crop labels remain transfer-only; acquisition does not promote them to Cannabis causal ground truth.']
    (out / f'{did}_phase6_summary.md').write_text('\n'.join(summary), encoding='utf-8')
    checks = []
    for p in sorted(out.iterdir()):
        if p.is_file() and not p.name.endswith('_checksums.sha256'):
            checks.append(f'{digest(p)}  {p.name}')
    (out / f'{did}_phase6_checksums.sha256').write_text('\n'.join(checks) + '\n', encoding='utf-8')
    print(json.dumps(status, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
