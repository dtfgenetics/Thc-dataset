#!/usr/bin/env python3
"""
Copy or extract files from bulk_acquisition/phase2 into dataset/acquisition/acquired/<DS-ID>/
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PHASE2 = ROOT / 'bulk_acquisition' / 'phase2'
DEST_ROOT = ROOT / 'dataset' / 'acquisition' / 'acquired'
DEST_ROOT.mkdir(parents=True, exist_ok=True)

for p in sorted(PHASE2.iterdir()):
    name = p.name
    if name.startswith('DS') and '_' in name:
        ds = name.split('_', 1)[0]
        dest = DEST_ROOT / ds
        dest.mkdir(parents=True, exist_ok=True)
        try:
            if p.is_file():
                shutil.copy2(p, dest / p.name)
                print(f'Copied {p.name} -> {dest}')
        except Exception as e:
            print(f'Error copying {p}: {e}')

print('Done')
