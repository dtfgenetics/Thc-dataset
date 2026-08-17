#!/usr/bin/env python3
import hashlib
import json
import mimetypes
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from PIL import Image

MANIFEST_PATH = pathlib.Path('images/reference/manifest.json')
PROFILE_MEDIA_PATH = pathlib.Path('data/profile-reference-media.json')
OUTPUT_DIR = pathlib.Path('images/reference/original')
MAX_BYTES = 20_000_000


def dhash64(image):
    gray = image.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value <<= 1
            if pixels[y * 9 + x] > pixels[y * 9 + x + 1]:
                value |= 1
    return f'dhash64:{value:016x}'


def dhash_distance(a, b):
    if not a or not b or ':' not in a or ':' not in b:
        return None
    try:
        return (int(a.split(':', 1)[1], 16) ^ int(b.split(':', 1)[1], 16)).bit_count()
    except ValueError:
        return None


def extension_for(content_type, url):
    ext = pathlib.Path(urllib.parse.urlparse(url).path).suffix.lower()
    if ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.tif', '.tiff'}:
        return ext
    return mimetypes.guess_extension(content_type) or '.img'


def fallback_urls(url):
    parsed = urllib.parse.urlparse(url)
    urls = []
    if parsed.hostname == 'www.mdpi.com':
        parts = parsed.path.strip('/').split('/')
        if len(parts) >= 3 and 'article_deploy' in parts:
            journal, article_id = parts[0], parts[1]
            rest = '/'.join(parts[2:])
            urls.append(f'https://mdpi-res.com/d_attachment/{journal}/{article_id}/{rest}')
    if parsed.hostname == 'media.springernature.com' and parsed.path.startswith('/full/'):
        urls.append(urllib.parse.urlunparse(parsed._replace(path=parsed.path.replace('/full/', '/lw685/', 1))))
    return urls


def fetch_image(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'DTF-THC-Dataset-Reference-Recovery/1.0 (+https://github.com/dtfgenetics/Thc-dataset)',
        'Accept': 'image/*',
        'Cache-Control': 'no-cache',
    })
    with urllib.request.urlopen(request, timeout=45) as response:
        content_type = response.headers.get_content_type()
        if not content_type.startswith('image/'):
            raise ValueError(f'non-image content type {content_type}')
        data = response.read(MAX_BYTES + 1)
        resolved = response.geturl()
    if not data or len(data) > MAX_BYTES:
        raise ValueError(f'invalid image byte size {len(data)}')
    return data, content_type, resolved


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    profile_media = json.loads(PROFILE_MEDIA_PATH.read_text(encoding='utf-8'))
    rich_by_id = {row['id']: row for row in profile_media if row.get('id')}
    records = {row['id']: row for row in manifest.get('records', []) if row.get('id')}
    unavailable = {row['id']: row for row in manifest.get('unavailable', []) if row.get('id')}

    recovered = []
    still_unavailable = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for asset_id in sorted(unavailable):
        status = unavailable[asset_id]
        rich = rich_by_id.get(asset_id)
        if not rich:
            still_unavailable.append({**status, 'recovery': 'no-rich-profile-media-record'})
            continue
        alternatives = fallback_urls(status.get('source_image_url') or rich.get('url', ''))
        if not alternatives:
            still_unavailable.append({**status, 'recovery': 'no-approved-publisher-fallback'})
            continue

        expected_sha = rich.get('sha256')
        expected_phash = rich.get('perceptualHash')
        accepted = None
        attempts = []

        for url in alternatives:
            print(f'RECOVERY_FETCH {asset_id} {url}')
            try:
                data, content_type, resolved = fetch_image(url)
                temp = OUTPUT_DIR / f'.recover-{asset_id}{extension_for(content_type, resolved)}'
                temp.write_bytes(data)
                with Image.open(temp) as image:
                    image.verify()
                with Image.open(temp) as image:
                    width, height = image.size
                    fmt = image.format
                    phash = dhash64(image)
                sha = hashlib.sha256(data).hexdigest()
                distance = dhash_distance(expected_phash, phash)
                exact = bool(expected_sha and sha == expected_sha)
                visual_match = bool(expected_phash and distance is not None and distance <= 4)
                if not exact and not visual_match:
                    temp.unlink(missing_ok=True)
                    attempts.append({'url': url, 'result': 'fingerprint-mismatch', 'sha256': sha, 'perceptualHash': phash, 'dhashDistance': distance})
                    continue
                final_path = OUTPUT_DIR / f'{asset_id}{extension_for(content_type, resolved)}'
                if final_path != temp:
                    final_path.write_bytes(data)
                    temp.unlink(missing_ok=True)
                accepted = {
                    'id': asset_id,
                    'issue_slug': rich.get('issueSlug'),
                    'repository_path': str(final_path),
                    'source_image_url': rich.get('url'),
                    'resolved_image_url': resolved,
                    'source_article': rich.get('sourceUrl'),
                    'caption': rich.get('caption') or rich.get('alt') or rich.get('diagnosticLabel'),
                    'creator': rich.get('creator') or 'See source article',
                    'license': rich.get('license'),
                    'required_attribution': rich.get('requiredAttribution'),
                    'confirmation': rich.get('confirmation'),
                    'limitations': rich.get('useLimitations'),
                    'diagnostic_label': rich.get('diagnosticLabel'),
                    'host_species': rich.get('hostSpecies'),
                    'host_context': rich.get('hostContext'),
                    'view': rich.get('view'),
                    'stage': rich.get('stage'),
                    'severity': rich.get('severity'),
                    'intended_use': 'reference-only',
                    'trainingEligible': False,
                    'sha256': sha,
                    'perceptual_hash': phash,
                    'bytes': len(data),
                    'mime_type': content_type,
                    'width': width,
                    'height': height,
                    'image_format': fmt,
                    'origin_registry': str(PROFILE_MEDIA_PATH),
                    'drift_status': 'exact-curated-byte-match' if exact else 'official-publisher-alternate-render-visual-match',
                    'verification_status': 'publisher-fallback-validated-hashed-and-persisted',
                    'expected_sha256': expected_sha,
                    'expected_perceptual_hash': expected_phash,
                    'dhash_distance_from_curated': distance,
                }
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                attempts.append({'url': url, 'result': str(exc)})

        if accepted:
            records[asset_id] = accepted
            recovered.append(asset_id)
            print(f"RECOVERED {asset_id} {accepted['width']}x{accepted['height']} {accepted['drift_status']}")
        else:
            still_unavailable.append({**status, 'recovery': 'fallbacks-failed', 'recoveryAttempts': attempts})
            print(f'REMAINS_UNAVAILABLE {asset_id}')

    output = {
        **manifest,
        'schemaVersion': '1.3.0',
        'status': 'reference-only-persisted-with-publisher-fallbacks',
        'recordCount': len(records),
        'unavailableCount': len(still_unavailable),
        'trainingEligibleCount': 0,
        'recoveredPublisherFallbackCount': len(recovered),
        'recoveredPublisherFallbackIds': recovered,
        'records': sorted(records.values(), key=lambda row: row['id']),
        'unavailable': sorted(still_unavailable, key=lambda row: row['id']),
    }
    MANIFEST_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'REFERENCE_BINARY_COUNT={len(records)}')
    print(f'REFERENCE_UNAVAILABLE_COUNT={len(still_unavailable)}')
    print(f'REFERENCE_RECOVERED_COUNT={len(recovered)}')


if __name__ == '__main__':
    main()
