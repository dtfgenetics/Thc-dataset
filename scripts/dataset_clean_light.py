#!/usr/bin/env python3
"""
Lightweight dataset cleaning and QA
- Computes sha256, dHash/pHash/aHash (via imagehash if installed, otherwise a Pillow-only dHash),
  color histograms, and SSIM (via scikit-image if available).
- Produces CSV inventory, JSON QA summary, and a short markdown summary.

Usage:
  python scripts\dataset_clean_light.py --root DATASET_ROOT --out OUTDIR

Designed to run on modest hosts (CPU-only). For very large datasets, use the --sample option
or run on a more powerful machine.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageOps

# Optional dependencies
try:
    import imagehash
    HAS_IMAGEHASH = True
except Exception:
    HAS_IMAGEHASH = False

try:
    from skimage.metrics import structural_similarity as ssim
    import numpy as np
    HAS_SKIMAGE = True
except Exception:
    HAS_SKIMAGE = False

IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def pillow_dhash(path: Path) -> int:
    # 9x8 grayscale resize like typical dHash implementations
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
        px = list(im.getdata())
    x = 0
    for y in range(8):
        row = px[y * 9:(y + 1) * 9]
        for i in range(8):
            x = (x << 1) | int(row[i] > row[i + 1])
    return x


def int_from_hashobj(hobj) -> int:
    # imagehash returns ImageHash object; convert to int
    try:
        return int(str(hobj), 16)
    except Exception:
        # fallback: use bits attribute if present
        if hasattr(hobj, 'hash'):
            arr = hobj.hash.flatten()
            out = 0
            for b in arr:
                out = (out << 1) | int(bool(b))
            return out
        raise


def compute_hashes(path: Path) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if HAS_IMAGEHASH:
        try:
            ah = imagehash.average_hash(Image.open(path))
            ph = imagehash.phash(Image.open(path))
            dh = imagehash.dhash(Image.open(path))
            out['ahash'] = int_from_hashobj(ah)
            out['phash'] = int_from_hashobj(ph)
            out['dhash'] = int_from_hashobj(dh)
            return out
        except Exception:
            # fallthrough to pillow dhash
            pass
    # fallback
    out['dhash'] = pillow_dhash(path)
    out['ahash'] = None
    out['phash'] = None
    return out


def color_hist(path: Path, size: Tuple[int, int] = (256, 256), bins: int = 32) -> List[float]:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert('RGB').resize(size, Image.Resampling.LANCZOS)
        arr = list(im.getdata())
    # build joint RGB histogram flattened
    hist = [0.0] * (bins * 3)
    for r, g, b in arr:
        ri = int(r * (bins - 1) / 255)
        gi = int(g * (bins - 1) / 255)
        bi = int(b * (bins - 1) / 255)
        hist[ri] += 1
        hist[bins + gi] += 1
        hist[2 * bins + bi] += 1
    total = sum(hist) or 1.0
    return [x / total for x in hist]


def hist_distance(h1: List[float], h2: List[float]) -> float:
    # Euclidean distance between two normalized histograms
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(h1, h2)))


def compute_ssim(a_path: Path, b_path: Path) -> float | None:
    if not HAS_SKIMAGE:
        return None
    try:
        with Image.open(a_path) as A, Image.open(b_path) as B:
            A = ImageOps.exif_transpose(A).convert('L').resize((256, 256), Image.Resampling.LANCZOS)
            B = ImageOps.exif_transpose(B).convert('L').resize((256, 256), Image.Resampling.LANCZOS)
            a = np.asarray(A, dtype=np.float32)
            b = np.asarray(B, dtype=np.float32)
            val = ssim(a, b)
            return float(val)
    except Exception:
        return None


def hamming_distance(x: int, y: int) -> int:
    return (x ^ y).bit_count()


def find_near_duplicates(rows: List[dict], dhash_threshold: int = 4, hist_threshold: float = 0.35, sample_limit: int = 500) -> Tuple[List[Tuple[int, int, int]], List[dict]]:
    # Returns list of (i,j,distance) where distance is dhash hamming
    # and a sample dict of cross-class conflicts
    n = len(rows)
    near = []
    samples = []
    for i in range(n):
        hi = rows[i].get('dhash')
        if hi is None:
            continue
        for j in range(i + 1, n):
            hj = rows[j].get('dhash')
            if hj is None:
                continue
            d = hamming_distance(hi, hj)
            if d <= dhash_threshold:
                # check color hist distance as a secondary filter
                hd = hist_distance(rows[i]['hist'], rows[j]['hist']) if ('hist' in rows[i] and 'hist' in rows[j]) else 0.0
                if hd <= hist_threshold:
                    near.append((i, j, d))
                    if rows[i]['classFolder'] != rows[j]['classFolder'] and len(samples) < sample_limit:
                        s = {'a': rows[i]['relativePath'], 'b': rows[j]['relativePath'], 'classA': rows[i]['classFolder'], 'classB': rows[j]['classFolder'], 'dhash': d, 'histDist': hd}
                        # optionally compute SSIM if available and it is a cross-class candidate
                        ssim_val = compute_ssim(Path(rows[i]['absPath']), Path(rows[j]['absPath']))
                        if ssim_val is not None:
                            s['ssim'] = ssim_val
                        samples.append(s)
    return near, samples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, help='Dataset root directory containing class subfolders')
    ap.add_argument('--out', required=True, help='Output directory for reports')
    ap.add_argument('--dhash-threshold', type=int, default=4, help='dHash Hamming distance threshold for near-duplicates')
    ap.add_argument('--hist-threshold', type=float, default=0.35, help='Color histogram euclidean distance threshold (normalized)')
    ap.add_argument('--sample', type=int, default=0, help='If >0, process only this many images (random)')

    args = ap.parse_args()
    root = Path(args.root).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    imgs = sorted(p for p in root.rglob('*') if p.suffix.lower() in IMG_EXT and p.is_file())
    if args.sample and args.sample > 0:
        imgs = imgs[:args.sample]

    rows = []
    sha_groups: Dict[str, List[int]] = defaultdict(list)
    classes = Counter()
    bad = []

    for idx, p in enumerate(imgs):
        rel = p.relative_to(root).as_posix()
        class_folder = p.parent.name
        try:
            s = sha256(p)
            hashes = compute_hashes(p)
            hist = color_hist(p)
            rows.append({'index': idx, 'relativePath': rel, 'absPath': str(p), 'classFolder': class_folder, 'sizeBytes': p.stat().st_size, 'sha256': s, 'dhash': hashes.get('dhash'), 'phash': hashes.get('phash'), 'ahash': hashes.get('ahash'), 'hist': hist})
            sha_groups[s].append(idx)
            classes[class_folder] += 1
        except Exception as exc:
            bad.append({'path': rel, 'error': str(exc)})

    exact_groups = [g for g in sha_groups.values() if len(g) > 1]
    exact_conflicts = []
    for g in exact_groups:
        labs = {rows[i]['classFolder'] for i in g}
        if len(labs) > 1:
            exact_conflicts.append({'sha256': rows[g[0]]['sha256'], 'members': [{'path': rows[i]['relativePath'], 'class': rows[i]['classFolder']} for i in g]})

    near_pairs, cross_samples = find_near_duplicates(rows, dhash_threshold=args.dhash_threshold, hist_threshold=args.hist_threshold)

    # Build components (union-find) to show connected near-duplicate components
    parent = list(range(len(rows)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra = find(a); rb = find(b)
        if ra != rb:
            parent[rb] = ra

    for i, j, d in near_pairs:
        union(i, j)

    comps = defaultdict(list)
    for i in range(len(rows)):
        comps[find(i)].append(i)
    near_components = sum(1 for g in comps.values() if len(g) > 1)

    # Write inventory CSV
    csv_path = out / 'image_inventory.csv'
    csv_fields = ['index', 'relativePath', 'classFolder', 'sizeBytes', 'sha256', 'dhash', 'phash', 'ahash']
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=csv_fields)
        w.writeheader()
        for r in rows:
            row = {k: r.get(k) for k in csv_fields}
            w.writerow(row)

    qa = {
        'createdAt': str(__import__('datetime').datetime.utcnow().isoformat() + 'Z'),
        'datasetRoot': str(root),
        'imageCount': len(rows),
        'classFolderCounts': dict(classes),
        'badImageCount': len(bad),
        'badImages': bad,
        'uniqueSha256Count': len(sha_groups),
        'exactDuplicateGroupCount': len(exact_groups),
        'exactCrossClassConflicts': exact_conflicts,
        'nearDuplicateEdgeCountDhashLE{}'.format(args.dhash_threshold): len(near_pairs),
        'nearDuplicateComponentCount': near_components,
        'crossClassNearDuplicateSample': cross_samples,
        'trainingGate': 'HOLD pending human review of exact and near-duplicate cross-class conflicts and leakage-safe split'
    }

    (out / 'qa.json').write_text(json.dumps(qa, indent=2), encoding='utf-8')

    summary_lines = [f'# Dataset Cleaning QA', '', f'Dataset root: {root}', f'Decoded images: {len(rows)}', f'Unique payloads (SHA-256): {len(sha_groups)}', f'Exact duplicate groups: {len(exact_groups)}', f"dHash<={args.dhash_threshold} edges: {len(near_pairs)}", f'Near-duplicate components: {near_components}', '', 'Training remains on HOLD pending human review of cross-class conflicts and leakage-safe split.']
    (out / 'summary.md').write_text('\n'.join(summary_lines), encoding='utf-8')

    print(json.dumps(qa, indent=2))


if __name__ == '__main__':
    main()
