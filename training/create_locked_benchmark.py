#!/usr/bin/env python3
"""Create a held-out benchmark split from the leakage-safe manifest.

The benchmark set is intentionally reserved from the training pipeline. It keeps the
same row schema as the split-safe manifest but marks all selected rows as split='benchmark'.
A deterministic group-based selection keeps the benchmark locked and reproducible.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / 'training' / 'leakage_safe_split.csv'
OUTPUT_PATH = ROOT / 'training' / 'locked_benchmark_manifest.csv'
SUMMARY_PATH = ROOT / 'training' / 'locked_benchmark_summary.json'


def build_benchmark_groups(rows: list[dict], max_percent: float = 0.15) -> set[str]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        group_id = row.get('group_id', '').strip()
        if group_id:
            groups[group_id].append(row)

    ordered_groups = sorted(groups.keys(), key=lambda gid: hashlib.sha256(gid.encode('utf-8')).hexdigest())
    target_count = max(1, int(round(len(ordered_groups) * max_percent)))
    benchmark_groups = set(ordered_groups[:target_count])
    return benchmark_groups


def load_rows() -> list[dict]:
    with SOURCE_PATH.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def main() -> None:
    rows = load_rows()
    if not rows:
        raise SystemExit(f'No rows found in {SOURCE_PATH}')

    benchmark_groups = build_benchmark_groups(rows)
    benchmark_rows: list[dict] = []
    for row in rows:
        updated = dict(row)
        if updated.get('group_id') in benchmark_groups:
            updated['split'] = 'benchmark'
            updated['benchmark_status'] = 'locked'
            updated['benchmark_reason'] = 'held_out_for_final_evaluation'
        else:
            updated['benchmark_status'] = 'training_ready'
            updated['benchmark_reason'] = 'not_benchmark'
        benchmark_rows.append(updated)

    fieldnames = list(rows[0].keys()) + ['benchmark_status', 'benchmark_reason']
    with OUTPUT_PATH.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(benchmark_rows)

    benchmark_count = sum(1 for row in benchmark_rows if row.get('split') == 'benchmark')
    label_counts = Counter(row.get('label', '') for row in benchmark_rows if row.get('split') == 'benchmark')
    summary = {
        'source_manifest': str(SOURCE_PATH.relative_to(ROOT)),
        'output_manifest': str(OUTPUT_PATH.relative_to(ROOT)),
        'total_rows': len(benchmark_rows),
        'benchmark_rows': benchmark_count,
        'benchmark_groups': len({row.get('group_id') for row in benchmark_rows if row.get('split') == 'benchmark'}),
        'label_counts': dict(sorted(label_counts.items())),
        'policy': {
            'locked_benchmark_required': True,
            'benchmark_is_excluded_from_training': True,
            'benchmark_is_reproducible': True,
            'benchmark_is_untouched_by_tuning': True,
        },
    }

    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f'Wrote {benchmark_count} benchmark rows to {OUTPUT_PATH}')
    print(f'Wrote summary to {SUMMARY_PATH}')


if __name__ == '__main__':
    main()
