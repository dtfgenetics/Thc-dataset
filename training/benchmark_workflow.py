#!/usr/bin/env python3
"""Build a benchmark/evaluation summary for the conservative plant-health pipeline.

This keeps a locked benchmark workflow visible in the repo: it records split counts,
unique labels, duplicate or leakage-risk signals, and whether the dataset is ready
for a held-out evaluation set.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / 'training' / 'leakage_safe_split.csv'
OUTPUT_PATH = ROOT / 'training' / 'benchmark_summary.json'


def load_rows() -> list[dict]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f'Manifest not found: {MANIFEST_PATH}')

    with MANIFEST_PATH.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def main() -> None:
    rows = load_rows()
    split_counts = Counter(row.get('split', '') for row in rows if row.get('split'))
    labels = Counter(row.get('label', '') for row in rows if row.get('label'))
    groups = Counter(row.get('group_id', '') for row in rows if row.get('group_id'))
    duplicate_hashes = [count for count in Counter(row.get('sha256', '') for row in rows if row.get('sha256')).values() if count > 1]

    total_images = len(rows)
    unique_hashes = len({row.get('sha256', '') for row in rows if row.get('sha256')})
    unique_groups = len(groups)
    benchmark_ready = (
        total_images > 0
        and split_counts.get('train', 0) > 0
        and split_counts.get('val', 0) > 0
        and split_counts.get('test', 0) > 0
        and unique_hashes == total_images
        and len(labels) >= 2
        and unique_groups >= max(3, len(labels))
        and not duplicate_hashes
    )

    summary = {
        'dataset_manifest': str(MANIFEST_PATH.relative_to(ROOT)),
        'total_rows': total_images,
        'unique_hashes': unique_hashes,
        'unique_groups': unique_groups,
        'label_count': len(labels),
        'top_labels': labels.most_common(10),
        'split_counts': dict(sorted(split_counts.items())),
        'issues': {
            'duplicate_hashes_found': bool(duplicate_hashes),
            'duplicate_hash_count': len(duplicate_hashes),
            'group_overlap_risk': unique_groups < len(labels) * 3,
            'has_train_val_test': all(split_counts.get(key, 0) > 0 for key in ('train', 'val', 'test')),
        },
        'benchmark_ready': benchmark_ready,
        'policy': {
            'locked_benchmark_required': True,
            'no_leakage_between_train_val_test': True,
            'user_uploads_not_used_for_training': True,
            'human_review_required_before_production_labels': True,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f'Wrote benchmark summary to {OUTPUT_PATH}')
    print(f'benchmark_ready={benchmark_ready}')


if __name__ == '__main__':
    main()
