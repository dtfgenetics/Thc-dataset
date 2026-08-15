#!/usr/bin/env python3
"""Compute pixel-level metadata for image references and training candidates.

This adds the missing metadata layer needed for better accuracy: image geometry,
color statistics, brightness/contrast, entropy, and focus-like sharpness. This does
not replace curated labels, but it provides the missing quantitative signal for
feature-based filtering and quality checks.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / 'training' / 'leakage_safe_split.csv'
DEFAULT_OUTPUT_CSV = ROOT / 'training' / 'enriched_image_metadata.csv'
DEFAULT_OUTPUT_JSON = ROOT / 'training' / 'enriched_image_metadata_summary.json'


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def compute_entropy(values):
    hist, _ = np.histogram(values, bins=256, range=(0, 256))
    hist = hist / max(1, hist.sum())
    hist = hist[hist > 0]
    return float(-(hist * np.log2(hist)).sum())


def compute_laplacian_variance(image):
    gray = np.asarray(ImageOps.grayscale(image), dtype=np.float32)
    grad_x = np.abs(np.gradient(gray, axis=1))
    grad_y = np.abs(np.gradient(gray, axis=0))
    lap = grad_x + grad_y
    return float(lap.var()) if lap.size else 0.0


def compute_image_features(path: Path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert('RGB')
        arr = np.asarray(img, dtype=np.float32)

    height, width, _ = arr.shape
    rgb = arr.reshape(-1, 3)
    mean = rgb.mean(axis=0)
    std = rgb.std(axis=0)
    grayscale = np.dot(rgb, [0.299, 0.587, 0.114])

    brightness = float(grayscale.mean())
    contrast = float(grayscale.std())
    entropy = float(compute_entropy(grayscale.astype(np.uint8).ravel()))
    sharpness = compute_laplacian_variance(Image.fromarray(np.uint8(arr)))
    aspect_ratio = float(width / height) if height else 0.0
    dark_ratio = float(np.mean(grayscale < 40))
    bright_ratio = float(np.mean(grayscale > 220))

    return {
        'width': width,
        'height': height,
        'aspect_ratio': round(aspect_ratio, 4),
        'mean_r': round(float(mean[0]), 4),
        'mean_g': round(float(mean[1]), 4),
        'mean_b': round(float(mean[2]), 4),
        'std_r': round(float(std[0]), 4),
        'std_g': round(float(std[1]), 4),
        'std_b': round(float(std[2]), 4),
        'brightness': round(brightness, 4),
        'contrast': round(contrast, 4),
        'entropy': round(entropy, 4),
        'sharpness': round(sharpness, 4),
        'dark_ratio': round(dark_ratio, 4),
        'bright_ratio': round(bright_ratio, 4),
    }


def main() -> None:
    input_path = DEFAULT_INPUT
    rows = []
    with input_path.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            image_path = ROOT / row['image_path']
            if not image_path.exists():
                continue
            features = compute_image_features(image_path)
            merged = {**row, **features}
            rows.append(merged)

    fieldnames = [
        'dataset_id', 'image_path', 'filename', 'label', 'group_id', 'plant_id',
        'dataset_rel_path', 'label_source', 'view', 'width', 'height', 'aspect_ratio',
        'mean_r', 'mean_g', 'mean_b', 'std_r', 'std_g', 'std_b', 'brightness',
        'contrast', 'entropy', 'sharpness', 'dark_ratio', 'bright_ratio', 'sha256',
        'split', 'source_status'
    ]
    with DEFAULT_OUTPUT_CSV.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        'generated_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'count': len(rows),
        'splits': dict(Counter(row['split'] for row in rows)),
        'labels': dict(Counter(row['label'] for row in rows).most_common(12)),
        'dataset_ids': dict(Counter(row['dataset_id'] for row in rows).most_common(10)),
        'pixel_metrics': {
            'brightness_mean': round(float(np.mean([safe_float(r['brightness']) for r in rows])), 4),
            'contrast_mean': round(float(np.mean([safe_float(r['contrast']) for r in rows])), 4),
            'entropy_mean': round(float(np.mean([safe_float(r['entropy']) for r in rows])), 4),
        },
    }
    DEFAULT_OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(rows)} row metadata summary to {DEFAULT_OUTPUT_CSV}')
    print(f'Wrote summary JSON to {DEFAULT_OUTPUT_JSON}')


if __name__ == '__main__':
    main()
