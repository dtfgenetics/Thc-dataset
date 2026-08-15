#!/usr/bin/env python3
"""Build a searchable JSON index for image-based reference media.

This script scans the dataset acquisition folders and emits a compact metadata index
that can be used by a UI or API to search reference images by dataset ID, issue label,
folder name, or file name.

Usage:
    python scripts/build_reference_image_index.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"Pillow is required to read image dimensions: {exc}")

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEARCH_ROOT = ROOT / 'dataset' / 'acquisition' / 'acquired'
OUTPUT_PATH = ROOT / 'dataset' / 'catalog' / 'reference-image-index.json'


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def image_dimensions(path: Path) -> Dict[str, int]:
    with Image.open(path) as img:
        width, height = img.size
        return {'width': int(width), 'height': int(height)}


def infer_dataset_id(path: Path) -> str | None:
    rel = path.relative_to(ROOT)
    for part in rel.parts:
        if part.startswith('DS-') or part.startswith('DS'):
            return part
    return None


def infer_labels(path: Path, dataset_id: str | None) -> List[str]:
    labels: List[str] = []
    rel = path.relative_to(ROOT)
    for part in rel.parts:
        if part.startswith('DS-') or part.startswith('DS'):
            continue
        if part == 'dataset' or part == 'acquisition' or part == 'acquired':
            continue
        clean = part.replace('_', ' ').replace('-', ' ')
        if clean and len(clean) > 2:
            labels.append(clean)
    if dataset_id:
        labels.append(dataset_id)
    return labels


def build_index(search_root: Path) -> Dict[str, Any]:
    images: List[Dict[str, Any]] = []
    for path in sorted(search_root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        rel = path.relative_to(ROOT).as_posix()
        dataset_id = infer_dataset_id(path)
        labels = infer_labels(path, dataset_id)
        dims = image_dimensions(path)
        entry = {
            'id': sha256_of(path)[:16],
            'datasetId': dataset_id,
            'path': rel,
            'filename': path.name,
            'folder': path.parent.name,
            'labels': labels,
            'searchText': ' '.join(labels),
            'sha256': sha256_of(path),
            'sizeBytes': path.stat().st_size,
            'extension': path.suffix.lower(),
            'width': dims['width'],
            'height': dims['height'],
        }
        images.append(entry)

    return {
        'generatedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'datasetRoot': search_root.relative_to(ROOT).as_posix(),
        'count': len(images),
        'images': images,
    }


def main() -> None:
    if not DEFAULT_SEARCH_ROOT.exists():
        raise SystemExit(f"Reference image root does not exist: {DEFAULT_SEARCH_ROOT}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = build_index(DEFAULT_SEARCH_ROOT)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Wrote {payload['count']} reference images to {OUTPUT_PATH}")


if __name__ == '__main__':
    main()
