#!/usr/bin/env python3
import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT = Path('model_tuning/config/adapter_combination_policy_v1.json')
SHA40 = re.compile(r'^[0-9a-f]{40}$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')
REQUIRED_SLICES = {
    'factuality', 'diagnostic', 'hallucination', 'citation_accuracy',
    'science', 'education', 'grounded_qa', 'regression'
}


def fail(message: str) -> None:
    raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_report_ref(cid: str, label: str, report: dict, report_root: Path) -> None:
    report_path = report.get('path')
    report_sha = report.get('sha256') or ''
    if not isinstance(report_path, str) or not report_path.strip() or not SHA256.fullmatch(report_sha):
        fail(f'{cid}: {label} requires a repository-relative path and exact sha256')

    relative = Path(report_path)
    if relative.is_absolute():
        fail(f'{cid}: {label} path must be repository-relative')

    root = report_root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        fail(f'{cid}: {label} path escapes report root')

    if not resolved.is_file():
        fail(f'{cid}: {label} file does not exist: {report_path}')
    actual_sha = sha256_file(resolved)
    if actual_sha != report_sha:
        fail(f'{cid}: {label} sha256 does not match file bytes')


def validate(path: Path, *, report_root: Path = Path('.')) -> None:
    data = json.loads(path.read_text())
    if data.get('schema_version') != 1:
        fail('schema_version must be 1')
    if data.get('benchmark') != 'model_tuning/eval/heldout_v2.jsonl':
        fail('adapter combination policy must use heldout_v2.jsonl')
    if set(data.get('required_slices') or []) != REQUIRED_SLICES:
        fail('required_slices must match all protected promotion slices')
    if data.get('minimum_aggregate_gain') != 0.02:
        fail('minimum_aggregate_gain must remain locked at 0.02 for v1')
    for key in ('require_no_slice_regression', 'require_reviewed_semantic_scores',
                'require_identical_runtime_contract', 'require_distinct_adapter_revisions',
                'require_adapter_artifact_sha256'):
        if data.get(key) is not True:
            fail(f'{key} must be true')

    seen = set()
    for item in data.get('combination_candidates') or []:
        cid = item.get('id')
        if not cid or cid in seen:
            fail(f'invalid or duplicate combination candidate id: {cid!r}')
        seen.add(cid)
        components = item.get('components') or []
        if len(components) < 2:
            fail(f'{cid}: combination requires at least two adapters')
        revisions = [c.get('revision') for c in components]
        if len(set(revisions)) != len(revisions):
            fail(f'{cid}: component adapter revisions must be distinct')
        seen_artifacts = set()
        for component in components:
            if not component.get('repository'):
                fail(f'{cid}: component repository is required')
            if not SHA40.fullmatch(component.get('revision') or ''):
                fail(f'{cid}: component revision must be an exact 40-char commit SHA')
            artifact_sha = component.get('adapter_artifact_sha256') or ''
            if not SHA256.fullmatch(artifact_sha):
                fail(f'{cid}: every component needs an exact adapter_artifact_sha256')
            if artifact_sha in seen_artifacts:
                fail(f'{cid}: adapter artifact hashes must be distinct')
            seen_artifacts.add(artifact_sha)
            report = component.get('promotion_report') or {}
            validate_report_ref(cid, 'component promotion report', report, report_root)
            if report.get('reviewed') is not True or report.get('passed_gate') is not True:
                fail(f'{cid}: every component must independently pass reviewed promotion')

        combo = item.get('combination_report') or {}
        if item.get('eligible_for_combination') is True:
            validate_report_ref(cid, 'combination report', combo, report_root)
            if combo.get('reviewed') is not True or combo.get('passed_gate') is not True:
                fail(f'{cid}: combination must pass reviewed promotion gate')
            gain = combo.get('aggregate_gain_vs_best_component')
            if not isinstance(gain, (int, float)) or gain < data['minimum_aggregate_gain']:
                fail(f'{cid}: combination must improve >= 0.02 over best component')
            regressions = combo.get('slice_regressions')
            if regressions != []:
                fail(f'{cid}: protected slice regressions are not allowed')
        elif combo:
            fail(f'{cid}: blocked candidate must not carry a promotion result')


def component(repository: str, revision: str, artifact_sha: str, report_path: str, report_sha: str) -> dict:
    return {
        'repository': repository,
        'revision': revision,
        'adapter_artifact_sha256': artifact_sha,
        'promotion_report': {
            'path': report_path,
            'sha256': report_sha,
            'reviewed': True,
            'passed_gate': True,
        },
    }


def self_test() -> None:
    import tempfile
    good = json.loads(DEFAULT.read_text())
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        p = root / 'policy.json'
        validate(DEFAULT)

        report_bytes = {
            'a.json': b'{"adapter":"a"}\n',
            'b.json': b'{"adapter":"b"}\n',
            'c.json': b'{"adapter":"c"}\n',
            'combo.json': b'{"combination":"a+b"}\n',
        }
        report_shas = {}
        for name, payload in report_bytes.items():
            target = root / name
            target.write_bytes(payload)
            report_shas[name] = hashlib.sha256(payload).hexdigest()

        def components() -> list[dict]:
            return [
                component('dtf/a', 'a' * 40, '1' * 64, 'a.json', report_shas['a.json']),
                component('dtf/b', 'c' * 40, '2' * 64, 'b.json', report_shas['b.json']),
            ]

        shared = json.loads(json.dumps(good))
        shared['combination_candidates'] = [
            {'id': 'a-plus-b', 'eligible_for_combination': False, 'components': components()},
            {'id': 'a-plus-c', 'eligible_for_combination': False, 'components': [
                component('dtf/a', 'a' * 40, '1' * 64, 'a.json', report_shas['a.json']),
                component('dtf/c', 'd' * 40, '3' * 64, 'c.json', report_shas['c.json']),
            ]},
        ]
        p.write_text(json.dumps(shared))
        validate(p, report_root=root)

        broken = json.loads(json.dumps(good))
        broken['combination_candidates'] = [{
            'id': 'bad-soup',
            'eligible_for_combination': True,
            'components': components(),
            'combination_report': {
                'path': 'combo.json', 'sha256': report_shas['combo.json'],
                'reviewed': True, 'passed_gate': True,
                'aggregate_gain_vs_best_component': 0.01, 'slice_regressions': []
            }
        }]
        p.write_text(json.dumps(broken))
        try:
            validate(p, report_root=root)
        except ValueError:
            pass
        else:
            fail('self-test expected sub-threshold combination gain to fail')

        broken = json.loads(json.dumps(good))
        broken['combination_candidates'] = [{
            'id': 'bad-regression',
            'eligible_for_combination': True,
            'components': components(),
            'combination_report': {
                'path': 'combo.json', 'sha256': report_shas['combo.json'],
                'reviewed': True, 'passed_gate': True,
                'aggregate_gain_vs_best_component': 0.03, 'slice_regressions': ['factuality']
            }
        }]
        p.write_text(json.dumps(broken))
        try:
            validate(p, report_root=root)
        except ValueError:
            pass
        else:
            fail('self-test expected protected slice regression to fail')

        broken = json.loads(json.dumps(good))
        missing_hash_components = components()
        missing_hash_components[0].pop('adapter_artifact_sha256')
        broken['combination_candidates'] = [{
            'id': 'missing-artifact-hash',
            'eligible_for_combination': False,
            'components': missing_hash_components,
        }]
        p.write_text(json.dumps(broken))
        try:
            validate(p, report_root=root)
        except ValueError as exc:
            assert 'adapter_artifact_sha256' in str(exc)
        else:
            fail('self-test expected missing adapter artifact hash to fail')

        broken = json.loads(json.dumps(good))
        duplicate_components = components()
        duplicate_components[1]['adapter_artifact_sha256'] = duplicate_components[0]['adapter_artifact_sha256']
        broken['combination_candidates'] = [{
            'id': 'duplicate-artifact',
            'eligible_for_combination': False,
            'components': duplicate_components,
        }]
        p.write_text(json.dumps(broken))
        try:
            validate(p, report_root=root)
        except ValueError as exc:
            assert 'artifact hashes must be distinct' in str(exc)
        else:
            fail('self-test expected duplicate adapter artifact hash to fail')

        broken = json.loads(json.dumps(good))
        stale_components = components()
        stale_components[0]['promotion_report']['sha256'] = 'f' * 64
        broken['combination_candidates'] = [{
            'id': 'stale-promotion-report',
            'eligible_for_combination': False,
            'components': stale_components,
        }]
        p.write_text(json.dumps(broken))
        try:
            validate(p, report_root=root)
        except ValueError as exc:
            assert 'sha256 does not match file bytes' in str(exc)
        else:
            fail('self-test expected stale promotion report hash to fail')

        broken = json.loads(json.dumps(good))
        broken['combination_candidates'] = [{
            'id': 'missing-combination-report',
            'eligible_for_combination': True,
            'components': components(),
            'combination_report': {
                'path': 'missing.json', 'sha256': 'e' * 64,
                'reviewed': True, 'passed_gate': True,
                'aggregate_gain_vs_best_component': 0.03, 'slice_regressions': []
            }
        }]
        p.write_text(json.dumps(broken))
        try:
            validate(p, report_root=root)
        except ValueError as exc:
            assert 'file does not exist' in str(exc)
        else:
            fail('self-test expected missing combination report file to fail')

        broken = json.loads(json.dumps(good))
        escape_components = components()
        escape_components[0]['promotion_report']['path'] = '../outside.json'
        broken['combination_candidates'] = [{
            'id': 'path-escape',
            'eligible_for_combination': False,
            'components': escape_components,
        }]
        p.write_text(json.dumps(broken))
        try:
            validate(p, report_root=root)
        except ValueError as exc:
            assert 'path escapes report root' in str(exc)
        else:
            fail('self-test expected report path escape to fail')


if __name__ == '__main__':
    try:
        if '--self-test' in sys.argv:
            self_test()
            print('adapter combination policy self-test: ok')
        else:
            validate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
            print('adapter combination policy: ok')
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f'adapter combination policy validation failed: {exc}', file=sys.stderr)
        sys.exit(1)
