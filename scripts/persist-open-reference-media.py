#!/usr/bin/env python3
import hashlib
import json
import mimetypes
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
from PIL import Image

ACQUISITION_DIR = pathlib.Path('dataset/acquisition')
PROFILE_MEDIA_PATH = pathlib.Path('data/profile-reference-media.json')
OUTPUT_DIR = pathlib.Path('images/reference/original')
MANIFEST_PATH = pathlib.Path('images/reference/manifest.json')
MAX_BYTES = 20_000_000
ALLOWED_HOSTS = {
    'academic.oup.com', 'oup.silverchair-cdn.com',
    'www.frontiersin.org', 'frontiersin.org',
    'pmc.ncbi.nlm.nih.gov', 'www.ncbi.nlm.nih.gov', 'cdn.ncbi.nlm.nih.gov',
    'www.mdpi.com', 'mdpi-res.com', 'media.springernature.com',
    'bugwoodcloud.org', 'content.ces.ncsu.edu',
    'commons.wikimedia.org', 'www.preprints.org',
}
ALLOWED_LICENSES = {
    'CC BY 4.0', 'CC BY 3.0', 'CC BY 3.0 US', 'CC BY',
    'Public domain (US federal government work)',
}
LICENSE_URLS = {
    'CC BY 4.0': 'https://creativecommons.org/licenses/by/4.0/',
    'CC BY 3.0': 'https://creativecommons.org/licenses/by/3.0/',
    'CC BY 3.0 US': 'https://creativecommons.org/licenses/by/3.0/us/',
    'CC BY': 'https://creativecommons.org/licenses/by/4.0/',
    'Public domain (US federal government work)': 'https://www.usa.gov/government-copyright',
}


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


def extension_for(content_type: str, final_url: str) -> str:
    ext = pathlib.Path(urllib.parse.urlparse(final_url).path).suffix.lower()
    if ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.tif', '.tiff'}:
        return ext
    return mimetypes.guess_extension(content_type) or '.img'


def existing_baseline():
    if not MANIFEST_PATH.is_file():
        return {}
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        return {row['id']: row for row in manifest.get('records', []) if row.get('id')}
    except Exception:
        return {}


def normalize_explicit_candidate(item, source_file):
    return {
        **item,
        'origin_registry': str(source_file),
        'required_fetch': True,
        'expected_sha256': None,
        'expected_perceptual_hash': None,
        'expected_width': None,
        'expected_height': None,
        'required_attribution': item.get('required_attribution'),
    }


def normalize_profile_media(item):
    if item.get('mediaType') != 'image':
        return None
    if item.get('displayPermission') != 'permitted' or item.get('trainingPermission') != 'permitted':
        return None
    license_name = item.get('license')
    if license_name not in ALLOWED_LICENSES:
        return None
    url = item.get('url')
    if not url:
        return None
    host = urllib.parse.urlparse(url).hostname
    if host not in ALLOWED_HOSTS:
        print(f"SKIP {item.get('id')} unsupported-host={host}")
        return None
    return {
        'id': item.get('id'),
        'issue_slug': item.get('issueSlug'),
        'image_url': url,
        'source_article': item.get('sourceUrl'),
        'caption': item.get('caption') or item.get('alt') or item.get('diagnosticLabel'),
        'creator': item.get('creator') or 'See required attribution and source article',
        'license': license_name,
        'license_url': LICENSE_URLS.get(license_name),
        'confirmation': item.get('confirmation'),
        'limitations': item.get('useLimitations'),
        'intended_use': 'reference-only',
        'required_attribution': item.get('requiredAttribution'),
        'diagnostic_label': item.get('diagnosticLabel'),
        'host_species': item.get('hostSpecies'),
        'host_context': item.get('hostContext'),
        'view': item.get('view'),
        'stage': item.get('stage'),
        'severity': item.get('severity'),
        'origin_registry': str(PROFILE_MEDIA_PATH),
        'required_fetch': False,
        'expected_sha256': item.get('sha256'),
        'expected_perceptual_hash': item.get('perceptualHash'),
        'expected_width': item.get('width'),
        'expected_height': item.get('height'),
    }


def load_candidates():
    by_id = {}
    if PROFILE_MEDIA_PATH.is_file():
        profile_media = json.loads(PROFILE_MEDIA_PATH.read_text(encoding='utf-8'))
        if not isinstance(profile_media, list):
            raise SystemExit(f'{PROFILE_MEDIA_PATH}: expected JSON array')
        for item in profile_media:
            normalized = normalize_profile_media(item)
            if normalized:
                if not normalized.get('id'):
                    raise SystemExit(f'{PROFILE_MEDIA_PATH}: approved media missing id')
                by_id[normalized['id']] = normalized

    for source_file in sorted(ACQUISITION_DIR.glob('verified-open-media-candidates*.json')):
        batch = json.loads(source_file.read_text(encoding='utf-8'))
        if not isinstance(batch, list):
            raise SystemExit(f'{source_file}: expected JSON array')
        for item in batch:
            if not isinstance(item, dict):
                raise SystemExit(f'{source_file}: every candidate must be an object')
            normalized = normalize_explicit_candidate(item, source_file)
            if not normalized.get('id'):
                raise SystemExit(f'{source_file}: candidate missing id')
            by_id[normalized['id']] = normalized

    if not by_id:
        raise SystemExit('No rights-cleared open-media candidates found.')
    return [by_id[key] for key in sorted(by_id)]


def unavailable_record(candidate, reason, http_status=None, preserved=False):
    return {
        'id': candidate.get('id'),
        'issue_slug': candidate.get('issue_slug'),
        'source_image_url': candidate.get('image_url'),
        'source_article': candidate.get('source_article'),
        'license': candidate.get('license'),
        'origin_registry': candidate.get('origin_registry'),
        'required_fetch': bool(candidate.get('required_fetch')),
        'reason': reason,
        'http_status': http_status,
        'previous_local_copy_preserved': preserved,
        'trainingEligible': False,
    }


def preserve_previous(candidate, previous, results):
    baseline = previous.get(candidate['id'])
    if not baseline:
        return False
    repository_path = baseline.get('repository_path')
    if not repository_path or not pathlib.Path(repository_path).is_file():
        return False
    preserved = dict(baseline)
    preserved['verification_status'] = 'previously-persisted-remote-temporarily-unavailable'
    preserved['trainingEligible'] = False
    results.append(preserved)
    return True


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = load_candidates()
    previous = existing_baseline()
    results = []
    unavailable = []

    for candidate in candidates:
        required = ['id', 'issue_slug', 'image_url', 'source_article', 'caption', 'creator', 'license', 'intended_use']
        missing = [key for key in required if not candidate.get(key)]
        if missing:
            raise SystemExit(f"{candidate.get('id')}: missing {missing}")
        if candidate['intended_use'] != 'reference-only':
            raise SystemExit(f"{candidate['id']}: only reference-only candidates may be persisted")
        if candidate['license'] not in ALLOWED_LICENSES:
            raise SystemExit(f"{candidate['id']}: unapproved license {candidate['license']}")

        parsed = urllib.parse.urlparse(candidate['image_url'])
        if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS:
            raise SystemExit(f"{candidate['id']}: non-allowlisted host {parsed.hostname}")

        print(f"FETCH {candidate['id']} {candidate['image_url']}")
        request = urllib.request.Request(candidate['image_url'], headers={
            'User-Agent': 'DTF-THC-Dataset-Reference-Persistence/1.3 (+https://github.com/dtfgenetics/Thc-dataset)',
            'Accept': 'image/*',
            'Cache-Control': 'no-cache',
        })
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                content_type = response.headers.get_content_type()
                if not content_type.startswith('image/'):
                    raise ValueError(f'non-image content type {content_type}')
                data = response.read(MAX_BYTES + 1)
                final_url = response.geturl()
            if not data or len(data) > MAX_BYTES:
                raise ValueError(f'invalid image byte size {len(data)}')
        except urllib.error.HTTPError as exc:
            if candidate.get('required_fetch'):
                raise SystemExit(f"{candidate['id']}: required image fetch failed HTTP {exc.code}")
            preserved = preserve_previous(candidate, previous, results)
            unavailable.append(unavailable_record(candidate, f'HTTP {exc.code}: {exc.reason}', exc.code, preserved))
            print(f"UNAVAILABLE {candidate['id']} HTTP {exc.code} preserved={preserved}")
            continue
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if candidate.get('required_fetch'):
                raise SystemExit(f"{candidate['id']}: required image fetch failed: {exc}")
            preserved = preserve_previous(candidate, previous, results)
            unavailable.append(unavailable_record(candidate, str(exc), None, preserved))
            print(f"UNAVAILABLE {candidate['id']} {exc} preserved={preserved}")
            continue

        safe_id = re.sub(r'[^A-Za-z0-9._-]+', '-', candidate['id']).strip('-')
        ext = extension_for(content_type, final_url)
        output_path = OUTPUT_DIR / f'{safe_id}{ext}'
        output_path.write_bytes(data)

        try:
            with Image.open(output_path) as image:
                image.verify()
            with Image.open(output_path) as image:
                width, height = image.size
                image_format = image.format
                perceptual_hash = dhash64(image)
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            if candidate.get('required_fetch'):
                raise SystemExit(f"{candidate['id']}: required image payload invalid: {exc}")
            preserved = preserve_previous(candidate, previous, results)
            unavailable.append(unavailable_record(candidate, f'invalid image payload: {exc}', None, preserved))
            print(f"UNAVAILABLE {candidate['id']} invalid-image preserved={preserved}")
            continue

        sha256 = hashlib.sha256(data).hexdigest()
        baseline = previous.get(candidate['id'])
        expected_sha = (baseline or {}).get('sha256') or candidate.get('expected_sha256')
        expected_phash = (baseline or {}).get('perceptual_hash') or candidate.get('expected_perceptual_hash')
        expected_width = (baseline or {}).get('width') or candidate.get('expected_width')
        expected_height = (baseline or {}).get('height') or candidate.get('expected_height')
        drift_status = 'new-or-byte-stable'
        if expected_sha and sha256 != expected_sha:
            dimensions_match = (not expected_width or width == expected_width) and (not expected_height or height == expected_height)
            if expected_phash and perceptual_hash == expected_phash and dimensions_match:
                drift_status = 'publisher-byte-reencoding-visual-stable'
            else:
                output_path.unlink(missing_ok=True)
                if candidate.get('required_fetch'):
                    raise SystemExit(
                        f"{candidate['id']}: required publisher visual drift; old sha={expected_sha} new sha={sha256} "
                        f"old phash={expected_phash} new phash={perceptual_hash} old dims={(expected_width, expected_height)} new dims={(width, height)}"
                    )
                preserved = preserve_previous(candidate, previous, results)
                unavailable.append(unavailable_record(candidate, 'publisher visual drift requires human review', None, preserved))
                print(f"UNAVAILABLE {candidate['id']} visual-drift preserved={preserved}")
                continue

        results.append({
            'id': candidate['id'],
            'issue_slug': candidate['issue_slug'],
            'repository_path': str(output_path),
            'source_image_url': candidate['image_url'],
            'resolved_image_url': final_url,
            'source_article': candidate['source_article'],
            'caption': candidate['caption'],
            'creator': candidate['creator'],
            'license': candidate['license'],
            'license_url': candidate.get('license_url'),
            'required_attribution': candidate.get('required_attribution'),
            'confirmation': candidate.get('confirmation'),
            'limitations': candidate.get('limitations'),
            'diagnostic_label': candidate.get('diagnostic_label'),
            'host_species': candidate.get('host_species'),
            'host_context': candidate.get('host_context'),
            'view': candidate.get('view'),
            'stage': candidate.get('stage'),
            'severity': candidate.get('severity'),
            'intended_use': 'reference-only',
            'trainingEligible': False,
            'sha256': sha256,
            'perceptual_hash': perceptual_hash,
            'bytes': len(data),
            'mime_type': content_type,
            'width': width,
            'height': height,
            'image_format': image_format,
            'origin_registry': candidate.get('origin_registry'),
            'drift_status': drift_status,
            'verification_status': 'downloaded-image-validated-hashed-and-persisted',
        })
        print(f"PERSISTED {candidate['id']} {width}x{height} {len(data)} bytes sha256={sha256} {drift_status}")

    # Never delete existing binaries merely because an upstream publisher is temporarily unavailable.
    # Orphan cleanup is a separate explicit review action.
    records_by_id = {row['id']: row for row in results}
    manifest = {
        'schemaVersion': '1.2.0',
        'status': 'reference-only-persisted-with-unavailable-tracking',
        'candidateCount': len(candidates),
        'recordCount': len(records_by_id),
        'unavailableCount': len(unavailable),
        'trainingEligibleCount': 0,
        'originRegistryCount': len({row.get('origin_registry') for row in records_by_id.values()}),
        'policy': 'These binaries are rights-cleared reference evidence only. Optional publisher outages are recorded and do not erase previously verified local copies. Persistence never makes a full figure or composite model-training eligible.',
        'records': sorted(records_by_id.values(), key=lambda item: item['id']),
        'unavailable': sorted(unavailable, key=lambda item: item['id']),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"REFERENCE_BINARY_COUNT={len(records_by_id)}")
    print(f"REFERENCE_UNAVAILABLE_COUNT={len(unavailable)}")


if __name__ == '__main__':
    main()
