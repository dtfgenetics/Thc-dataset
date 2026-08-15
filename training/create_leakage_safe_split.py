#!/usr/bin/env python3
"""Assign leakage-safe train/val/test splits at the group level.

Each row is assigned to the same split as its group_id. This prevents images from
one plant/session/time series from appearing in both train and validation.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / 'training' / 'metadata_manifest.csv'
OUTPUT_PATH = ROOT / 'training' / 'leakage_safe_split.csv'


def group_split_for(group_id: str) -> str:
    seed = int(hashlib.sha256(group_id.encode('utf-8')).hexdigest()[:8], 16)
    bucket = seed % 100
    if bucket < 70:
        return 'train'
    if bucket < 85:
        return 'val'
    return 'test'


def main() -> None:
    rows: list[dict] = []
    with MANIFEST_PATH.open('r', newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            split = group_split_for(row['group_id'])
            out = dict(row)
            out['split'] = split
            rows.append(out)

    fieldnames = list(rows[0].keys()) if rows else [
        'dataset_id', 'image_path', 'filename', 'label', 'group_id', 'plant_id',
        'dataset_rel_path', 'label_source', 'view', 'width', 'height', 'sha256', 'split', 'source_status'
    ]

    with OUTPUT_PATH.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'Wrote {len(rows)} rows to {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
