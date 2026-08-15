#!/usr/bin/env python3
"""
Extract archives from bulk_acquisition/phase1 into dataset/acquisition/acquired/<datasetId>
Handles .zip, .tar.gz and single files.
"""
from pathlib import Path
import zipfile, tarfile, shutil

ROOT = Path(__file__).resolve().parents[1]
PHASE1 = ROOT / 'bulk_acquisition' / 'phase1'
DEST_ROOT = ROOT / 'dataset' / 'acquisition' / 'acquired'
DEST_ROOT.mkdir(parents=True, exist_ok=True)

for p in sorted(PHASE1.iterdir()):
    name = p.name
    if name.startswith('DS-'):
        # dataset id prefix
        parts = name.split('_', 1)
        ds = parts[0]
        dest = DEST_ROOT / ds
        dest.mkdir(parents=True, exist_ok=True)
        try:
            if p.suffix.lower() in ['.zip']:
                with zipfile.ZipFile(p, 'r') as z:
                    z.extractall(dest)
                print(f'Extracted {p.name} -> {dest}')
            elif p.suffix.lower() in ['.gz', '.tgz'] or p.name.endswith('.tar.gz'):
                with tarfile.open(p, 'r:gz') as t:
                    t.extractall(dest)
                print(f'Extracted {p.name} -> {dest}')
            elif p.is_file():
                # copy single file
                shutil.copy2(p, dest / p.name)
                print(f'Copied {p.name} -> {dest}')
        except Exception as e:
            print(f'Error extracting {p}: {e}')

print('Done')
