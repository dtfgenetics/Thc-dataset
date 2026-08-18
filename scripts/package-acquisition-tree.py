#!/usr/bin/env python3
"""Create deterministic raw-dataset tar shards plus a provenance-ready manifest.

The script intentionally does not relabel or transform image bytes. It packages a source
working tree into roughly balanced shards so large public datasets can be moved into the
Drive raw lanes without depending on expiring external links.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tarfile
from pathlib import Path

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}


def sha256_file(path: Path, block: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        while True:
            chunk = fh.read(block)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def recursive_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())


def count_files(path: Path) -> tuple[int, int]:
    files = [path] if path.is_file() else [p for p in path.rglob('*') if p.is_file()]
    return len(files), sum(1 for p in files if p.suffix.lower() in IMAGE_EXTS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--prefix', required=True)
    ap.add_argument('--shards', required=True, type=int)
    ap.add_argument('--source-url', required=True)
    ap.add_argument('--license', required=True)
    ap.add_argument('--dataset-id', required=True)
    ap.add_argument('--source-revision', default='unknown')
    ap.add_argument('--notes', default='')
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.output_dir).resolve()
    if not root.is_dir():
        raise SystemExit(f'Root not found: {root}')
    if args.shards < 1:
        raise SystemExit('--shards must be >= 1')
    out.mkdir(parents=True, exist_ok=True)

    units = sorted(root.iterdir(), key=lambda p: p.name.lower())
    if not units:
        raise SystemExit(f'No source files under {root}')

    weighted = [(p, recursive_size(p)) for p in units]
    bins: list[list[tuple[Path, int]]] = [[] for _ in range(args.shards)]
    totals = [0] * args.shards
    for path, size in sorted(weighted, key=lambda item: (-item[1], item[0].name.lower())):
        idx = min(range(args.shards), key=lambda i: totals[i])
        bins[idx].append((path, size))
        totals[idx] += size

    shard_records = []
    for idx, members in enumerate(bins, start=1):
        if not members:
            continue
        tar_path = out / f'{args.prefix}-shard-{idx:02d}.tar'
        member_records = []
        file_count = image_count = 0
        with tarfile.open(tar_path, mode='w', format=tarfile.PAX_FORMAT) as tf:
            for path, raw_size in sorted(members, key=lambda item: item[0].name.lower()):
                tf.add(path, arcname=path.name, recursive=True)
                n_files, n_images = count_files(path)
                file_count += n_files
                image_count += n_images
                member_records.append({
                    'name': path.name,
                    'rawBytes': raw_size,
                    'fileCount': n_files,
                    'imageCount': n_images,
                })
        shard_records.append({
            'fileName': tar_path.name,
            'sha256': sha256_file(tar_path),
            'bytes': tar_path.stat().st_size,
            'fileCount': file_count,
            'imageCount': image_count,
            'members': member_records,
        })
        print(f'PACKAGED {tar_path.name} images={image_count} files={file_count} bytes={tar_path.stat().st_size}')

    manifest = {
        'schemaVersion': '1.0.0',
        'datasetId': args.dataset_id,
        'sourceUrl': args.source_url,
        'sourceRevision': args.source_revision,
        'license': args.license,
        'packagingPolicy': 'Raw source bytes are archived without image transformations. Archive SHA-256 verifies transport integrity; per-image hashing/deduplication occurs downstream before training admission.',
        'notes': args.notes,
        'rootName': root.name,
        'shardCount': len(shard_records),
        'totalArchiveBytes': sum(r['bytes'] for r in shard_records),
        'totalFiles': sum(r['fileCount'] for r in shard_records),
        'totalImages': sum(r['imageCount'] for r in shard_records),
        'shards': shard_records,
    }
    manifest_path = out / f'{args.prefix}-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: manifest[k] for k in ['datasetId', 'shardCount', 'totalArchiveBytes', 'totalFiles', 'totalImages']}, indent=2))


if __name__ == '__main__':
    main()
