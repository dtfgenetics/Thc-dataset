#!/usr/bin/env python3
"""Build a dataset metadata manifest for image-based diagnostic training.

This manifest is intentionally conservative: it records a file-level fingerprint,
image geometry, dataset ID, inferred class label, plant/session grouping, and the
path-derived label source. It does not claim scientific certainty from the file path
alone; the metadata is meant to enable clean split construction and review.
"""
from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / 'dataset' / 'acquisition' / 'acquired'
OUTPUT_PATH = ROOT / 'training' / 'metadata_manifest.csv'
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def infer_dataset_id(relative: Path) -> str:
    for part in relative.parts:
        if re.match(r'^DS-?\d+$', part, flags=re.IGNORECASE):
            return part.upper()
    return 'UNKNOWN'


def normalize_label(value: str) -> str:
    clean = value.replace('_', ' ').replace('-', ' ')
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean.lower()


def infer_label(relative: Path, dataset_id: str) -> str:
    parts = [normalize_label(part) for part in relative.parts]
    rel_text = ' '.join(parts)

    if 'hemp water stress' in rel_text:
        if 'healthy' in rel_text:
            return 'healthy'
        if 'water stress 3 days' in rel_text or '3 days' in rel_text:
            return 'water_stress_3_days'
        if 'water stress 6 days' in rel_text or '6 days' in rel_text:
            return 'water_stress_6_days'
        if 'water stress 9 days' in rel_text or '9 days' in rel_text:
            return 'water_stress_9_days'
    if 'hemp growth' in rel_text:
        return 'growth_time_series'

    for key in ['healthy', 'water stress', 'stress', 'deficiency', 'toxicity', 'disease', 'mold', 'fungal', 'pest', 'mite', 'root rot', 'symptom']:
        if key in rel_text:
            return key.replace(' ', '_')

    for part in reversed(relative.parts):
        clean = normalize_label(part)
        if clean and clean not in {'dataset', 'acquisition', 'acquired', dataset_id.lower()} and 'ds' not in clean:
            return clean.replace(' ', '_')

    return 'unknown'


def infer_plant_id(relative: Path) -> str:
    for part in relative.parts:
        if re.match(r'^(C\d+|P\d+|plant\d+|sample\d+)$', part, flags=re.IGNORECASE):
            return part
    return 'unknown_plant'


def infer_group_id(relative: Path, dataset_id: str, label: str) -> str:
    plant_id = infer_plant_id(relative)
    return f'{dataset_id}|{plant_id}|{label}'


def infer_view(relative: Path) -> str:
    text = ' '.join(part.lower() for part in relative.parts)
    if 'flower' in text or 'inflorescence' in text:
        return 'whole-plant'
    if 'leaf' in text or 'canopy' in text:
        return 'close-up'
    if 'root' in text:
        return 'root-crown'
    return 'whole-plant'


def build_manifest() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(IMAGE_ROOT.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue

        relative = path.relative_to(ROOT)
        dataset_id = infer_dataset_id(relative)
        label = infer_label(relative, dataset_id)
        width, height = 0, 0
        try:
            with Image.open(path) as img:
                width, height = img.size
        except Exception:
            width, height = 0, 0

        rows.append({
            'dataset_id': dataset_id,
            'image_path': path.relative_to(ROOT).as_posix(),
            'filename': path.name,
            'label': label,
            'group_id': infer_group_id(relative, dataset_id, label),
            'plant_id': infer_plant_id(relative),
            'dataset_rel_path': relative.parent.as_posix(),
            'label_source': 'path-derived',
            'view': infer_view(relative),
            'width': width,
            'height': height,
            'sha256': sha256_of(path),
            'split': '',
            'source_status': 'public-reference-or-acquired'
        })

    return rows


def main() -> None:
    rows = build_manifest()
    fieldnames = [
        'dataset_id', 'image_path', 'filename', 'label', 'group_id', 'plant_id',
        'dataset_rel_path', 'label_source', 'view', 'width', 'height', 'sha256', 'split', 'source_status'
    ]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote {len(rows)} rows to {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
