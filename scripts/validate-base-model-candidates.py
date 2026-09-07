#!/usr/bin/env python3
import json
import re
import sys
from datetime import date
from pathlib import Path

DEFAULT = Path('model_tuning/config/base_model_candidates_v1.json')
SHA40 = re.compile(r'^[0-9a-f]{40}$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')
ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
REQUIRED_SLICES = {
    'factuality', 'diagnostic', 'hallucination', 'citation_accuracy',
    'science', 'education', 'grounded_qa', 'regression'
}
ALLOWED_RESEARCH_STATUS = {'pinned_baseline', 'active_research', 'legacy_research'}
PIN_READINESS_KEYS = {
    'exact_revision_verified',
    'tokenizer_or_processor_verified',
    'chat_template_verified',
    'decoding_contract_verified',
    'dependency_lock_verified',
    'hardware_contract_verified',
    'heldout_rag_binding_verified',
}


def fail(message: str) -> None:
    raise ValueError(message)


def validate(path: Path) -> None:
    data = json.loads(path.read_text())
    if data.get('schema_version') != 1:
        fail('schema_version must be 1')
    contract = data.get('benchmark_contract') or {}
    if contract.get('heldout_path') != 'model_tuning/eval/heldout_v2.jsonl':
        fail('benchmark contract must use heldout_v2.jsonl')
    if set(contract.get('required_slices') or []) != REQUIRED_SLICES:
        fail('benchmark required_slices must match the locked promotion slices')

    candidates = data.get('candidates') or []
    if not candidates:
        fail('candidate registry is empty')
    ids = set()
    repos = set()
    eligible = []
    for item in candidates:
        cid = item.get('id')
        repo = item.get('repo_id')
        if not cid or cid in ids:
            fail(f'invalid or duplicate candidate id: {cid!r}')
        if not repo or repo in repos:
            fail(f'invalid or duplicate repo_id: {repo!r}')
        ids.add(cid); repos.add(repo)

        status = item.get('research_status')
        if status not in ALLOWED_RESEARCH_STATUS:
            fail(f'{cid}: research_status must be one of {sorted(ALLOWED_RESEARCH_STATUS)}')
        checked = item.get('evidence_checked_at')
        if not isinstance(checked, str) or not ISO_DATE.fullmatch(checked):
            fail(f'{cid}: evidence_checked_at must be YYYY-MM-DD')
        try:
            date.fromisoformat(checked)
        except ValueError:
            fail(f'{cid}: evidence_checked_at is not a valid calendar date')

        if not item.get('license') or not item.get('license_source'):
            fail(f'{cid}: license and license_source are required')
        if not str(item.get('license_source')).startswith('https://'):
            fail(f'{cid}: license_source must be an https URL')

        readiness = item.get('pin_readiness')
        if not isinstance(readiness, dict) or set(readiness) != PIN_READINESS_KEYS:
            fail(f'{cid}: pin_readiness must contain exactly {sorted(PIN_READINESS_KEYS)}')
        if any(type(value) is not bool for value in readiness.values()):
            fail(f'{cid}: every pin_readiness value must be boolean')

        benchmark_eligible = item.get('benchmark_eligible') is True
        training_eligible = item.get('training_eligible') is True
        frozen = item.get('runtime_contract_frozen') is True
        if training_eligible and not benchmark_eligible:
            fail(f'{cid}: training eligibility requires benchmark eligibility')
        if status == 'legacy_research' and (benchmark_eligible or training_eligible):
            fail(f'{cid}: legacy research candidates cannot be benchmark or training eligible')
        if status == 'pinned_baseline' and not benchmark_eligible:
            fail(f'{cid}: pinned baseline must be benchmark eligible')

        if benchmark_eligible:
            eligible.append(item)
            missing = sorted(key for key, value in readiness.items() if value is not True)
            if missing:
                fail(f'{cid}: benchmark eligibility requires all pin readiness gates; missing {missing}')
            if not frozen:
                fail(f'{cid}: benchmark eligibility requires a frozen runtime contract')
            if not SHA40.fullmatch(item.get('revision') or ''):
                fail(f'{cid}: eligible revision must be an exact 40-char commit SHA')
            if not SHA40.fullmatch(item.get('tokenizer_revision') or ''):
                fail(f'{cid}: eligible tokenizer_revision must be an exact 40-char commit SHA')
            if not SHA256.fullmatch(item.get('chat_template_sha256') or ''):
                fail(f'{cid}: eligible chat_template_sha256 must be pinned')
        else:
            if training_eligible:
                fail(f'{cid}: ineligible candidate cannot be training eligible')
            if frozen and not all(readiness.values()):
                fail(f'{cid}: runtime_contract_frozen cannot be true while pin readiness gates remain false')

    if len(eligible) != 1 or eligible[0].get('repo_id') != 'Qwen/Qwen3-8B':
        fail('v1 registry must fail closed with only pinned Qwen3-8B benchmark eligible')


def self_test() -> None:
    import tempfile
    good = json.loads(DEFAULT.read_text())
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'registry.json'

        broken = json.loads(json.dumps(good))
        broken['candidates'][1]['benchmark_eligible'] = True
        p.write_text(json.dumps(broken))
        try:
            validate(p)
        except ValueError:
            pass
        else:
            fail('self-test expected unpinned benchmark candidate to fail')

        broken = json.loads(json.dumps(good))
        broken['candidates'][1]['research_status'] = 'legacy_research'
        broken['candidates'][1]['training_eligible'] = True
        p.write_text(json.dumps(broken))
        try:
            validate(p)
        except ValueError:
            pass
        else:
            fail('self-test expected legacy training candidate to fail')

        broken = json.loads(json.dumps(good))
        broken['candidates'][1]['evidence_checked_at'] = '2026-02-31'
        p.write_text(json.dumps(broken))
        try:
            validate(p)
        except ValueError:
            pass
        else:
            fail('self-test expected invalid evidence date to fail')

        broken = json.loads(json.dumps(good))
        broken['candidates'][0]['pin_readiness']['hardware_contract_verified'] = False
        p.write_text(json.dumps(broken))
        try:
            validate(p)
        except ValueError:
            pass
        else:
            fail('self-test expected eligible candidate with incomplete pin readiness to fail')

        broken = json.loads(json.dumps(good))
        del broken['candidates'][1]['pin_readiness']['chat_template_verified']
        p.write_text(json.dumps(broken))
        try:
            validate(p)
        except ValueError:
            pass
        else:
            fail('self-test expected incomplete pin readiness schema to fail')


if __name__ == '__main__':
    try:
        if '--self-test' in sys.argv:
            self_test()
            print('base-model candidate registry self-test: ok')
        else:
            path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
            validate(path)
            print(f'base-model candidate registry: ok ({path})')
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f'base-model candidate registry validation failed: {exc}', file=sys.stderr)
        sys.exit(1)
