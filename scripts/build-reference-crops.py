#!/usr/bin/env python3
import hashlib
import json
import pathlib
from PIL import Image

SPEC_PATH = pathlib.Path('data/reference-crop-spec.json')
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


def main():
    spec = json.loads(SPEC_PATH.read_text(encoding='utf-8'))
    crops = spec.get('crops')
    if not isinstance(crops, list) or not crops:
        raise SystemExit('reference-crop-spec.json must contain a non-empty crops array')
    ids = [row.get('id') for row in crops]
    if None in ids or len(ids) != len(set(ids)):
        raise SystemExit('Crop IDs must be present and unique')

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

    manifest = {
        'schemaVersion': '1.0.0',
        'status': 'reference-only-panel-crops',
        'recordCount': len(records),
        'trainingEligibleCount': 0,
        'sourceGroupCount': len({row['sourceGroupId'] for row in records}),
        'policy': spec.get('policy'),
        'records': sorted(records, key=lambda item: item['id']),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"REFERENCE_CROP_COUNT={len(records)}")


if __name__ == '__main__':
    main()
