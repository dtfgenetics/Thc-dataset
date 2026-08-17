#!/usr/bin/env python3
import hashlib
import json
import pathlib
from PIL import Image

SPEC_PATH = pathlib.Path('data/reference-crop-spec.json')
GRID_SPEC_PATH = pathlib.Path('data/reference-grid-crop-spec.json')
OUT_DIR = pathlib.Path('images/reference/crops')
MANIFEST_PATH = pathlib.Path('images/reference/crops-manifest.json')


def dhash64(image: Image.Image) -> str:
    gray = image.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value <<= 1
            if pixels[y * 9 + x] > pixels[y * 9 + x + 1]:
                value |= 1
    return f'dhash64:{value:016x}'


def expand_grid_specs(grid_spec):
    expanded = []
    for grid in grid_spec.get('grids', []):
        xs = grid.get('xBands')
        ys = grid.get('yBands')
        columns = grid.get('columns')
        rows = grid.get('rows')
        if not all(isinstance(value, list) and value for value in [xs, ys, columns, rows]):
            raise SystemExit(f"{grid.get('id')}: incomplete grid geometry")
        if len(xs) != len(columns) or len(ys) != len(rows):
            raise SystemExit(f"{grid.get('id')}: geometry does not match column/row metadata")

        for ci, column in enumerate(columns):
            for ri, row in enumerate(rows):
                crop_id = f"crop-{column['id']}-{row['id']}"
                x0, x1 = xs[ci]
                y0, y1 = ys[ri]
                record = {
                    'id': crop_id,
                    'parentId': grid['parentId'],
                    'parentPath': grid['parentPath'],
                    'sourceGroupId': grid['sourceGroupId'],
                    'issueSlug': column['issueSlug'],
                    'box': [x0, y0, x1, y1],
                    'label': f"{column['id']}-{row['id']}",
                    'host': grid['host'],
                    'view': row.get('view', 'controlled-vegetative-symptom-panel'),
                    'severity': row.get('severity', 'source-context'),
                    'confirmation': grid['confirmation'],
                    'embeddedPanelLabel': False,
                    'trainingEligible': False,
                    'reason': grid['reason'],
                    'gridId': grid['id'],
                    'columnContext': {key: value for key, value in column.items() if key not in {'id', 'issueSlug'}},
                    'rowContext': {key: value for key, value in row.items() if key != 'id'},
                }
                expanded.append(record)
    return expanded


def main():
    spec = json.loads(SPEC_PATH.read_text(encoding='utf-8'))
    manual_crops = spec.get('crops')
    if not isinstance(manual_crops, list) or not manual_crops:
        raise SystemExit('reference-crop-spec.json must contain a non-empty crops array')

    grid_crops = []
    grid_policy = None
    if GRID_SPEC_PATH.is_file():
        grid_spec = json.loads(GRID_SPEC_PATH.read_text(encoding='utf-8'))
        grid_crops = expand_grid_specs(grid_spec)
        grid_policy = grid_spec.get('policy')

    crops = [*manual_crops, *grid_crops]
    ids = [row.get('id') for row in crops]
    if None in ids or len(ids) != len(set(ids)):
        raise SystemExit('Crop IDs must be present and globally unique')

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    expected = set()
    records = []

    for row in crops:
        parent = pathlib.Path(row['parentPath'])
        if not parent.is_file():
            raise SystemExit(f"{row['id']}: missing parent image {parent}")
        box = row.get('box')
        if not isinstance(box, list) or len(box) != 4 or not all(isinstance(v, int) for v in box):
            raise SystemExit(f"{row['id']}: box must contain four integer coordinates")

        with Image.open(parent) as source:
            width, height = source.size
            left, top, right, bottom = box
            if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                raise SystemExit(f"{row['id']}: crop {box} outside parent dimensions {(width, height)}")
            crop = source.crop((left, top, right, bottom)).convert('RGB')
            output = OUT_DIR / f"{row['id']}.png"
            crop.save(output, format='PNG', optimize=True)
            crop_width, crop_height = crop.size
            phash = dhash64(crop)

        data = output.read_bytes()
        expected.add(output.name)
        records.append({
            **row,
            'repositoryPath': str(output),
            'parentDimensions': [width, height],
            'cropDimensions': [crop_width, crop_height],
            'sha256': hashlib.sha256(data).hexdigest(),
            'perceptualHash': phash,
            'bytes': len(data),
            'derivedFormat': 'PNG',
            'derivativeStatus': 'pixel-bounds-generated-and-hashed',
            'trainingEligible': False,
        })
        print(f"CROP {row['id']} {crop_width}x{crop_height} {len(data)} bytes")

    for existing in OUT_DIR.glob('*'):
        if existing.is_file() and existing.name not in expected:
            existing.unlink()

    policies = [value for value in [spec.get('policy'), grid_policy] if value]
    manifest = {
        'schemaVersion': '1.1.0',
        'status': 'reference-only-panel-crops-expanded',
        'recordCount': len(records),
        'manualCropCount': len(manual_crops),
        'gridDerivedCropCount': len(grid_crops),
        'trainingEligibleCount': 0,
        'sourceGroupCount': len({row['sourceGroupId'] for row in records}),
        'policy': ' '.join(policies),
        'records': sorted(records, key=lambda item: item['id']),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"REFERENCE_CROP_COUNT={len(records)}")
    print(f"REFERENCE_MANUAL_CROP_COUNT={len(manual_crops)}")
    print(f"REFERENCE_GRID_CROP_COUNT={len(grid_crops)}")
    print(f"REFERENCE_CROP_SOURCE_GROUPS={manifest['sourceGroupCount']}")


if __name__ == '__main__':
    main()
