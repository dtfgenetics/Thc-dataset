#!/usr/bin/env python3
"""Build a simplified training manifest from the reference image catalog.

This is a starter pipeline for future image-classification work. It converts the
public reference index into a CSV manifest with path, dataset id, and class label.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / 'dataset' / 'catalog' / 'reference-image-index.json'
OUTPUT_PATH = ROOT / 'training' / 'reference_manifest.csv'


def main() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    rows = []
    for item in index.get('images', []):
        rows.append({
            'dataset_id': item.get('datasetId') or 'unknown',
            'class_label': (item.get('datasetId') or item.get('folder') or 'unknown').strip(),
            'image_path': item.get('path', ''),
            'filename': item.get('filename', ''),
            'sha256': item.get('sha256', ''),
            'source_url': '',
        })

    fieldnames = ['dataset_id', 'class_label', 'image_path', 'filename', 'sha256', 'source_url']
    with OUTPUT_PATH.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'Wrote {len(rows)} rows to {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
