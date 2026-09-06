#!/usr/bin/env python3
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


def validate(path: Path) -> None:
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
                'require_identical_runtime_contract', 'require_distinct_adapter_revisions'):
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
        for component in components:
            if not component.get('repository'):
                fail(f'{cid}: component repository is required')
            if not SHA40.fullmatch(component.get('revision') or ''):
                fail(f'{cid}: component revision must be an exact 40-char commit SHA')
            report = component.get('promotion_report') or {}
            if not report.get('path') or not SHA256.fullmatch(report.get('sha256') or ''):
                fail(f'{cid}: every component needs a hashed promotion report')
            if report.get('reviewed') is not True or report.get('passed_gate') is not True:
                fail(f'{cid}: every component must independently pass reviewed promotion')

        combo = item.get('combination_report') or {}
        if item.get('eligible_for_combination') is True:
            if not combo.get('path') or not SHA256.fullmatch(combo.get('sha256') or ''):
                fail(f'{cid}: eligibility requires a hashed combination report')
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


def self_test() -> None:
    import tempfile
    good = json.loads(DEFAULT.read_text())
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'policy.json'
        validate(DEFAULT)
        broken = json.loads(json.dumps(good))
        broken['combination_candidates'] = [{
            'id': 'bad-soup',
            'eligible_for_combination': True,
            'components': [
                {'repository': 'dtf/a', 'revision': 'a' * 40, 'promotion_report': {'path': 'a.json', 'sha256': 'b' * 64, 'reviewed': True, 'passed_gate': True}},
                {'repository': 'dtf/b', 'revision': 'c' * 40, 'promotion_report': {'path': 'b.json', 'sha256': 'd' * 64, 'reviewed': True, 'passed_gate': True}}
            ],
            'combination_report': {'path': 'combo.json', 'sha256': 'e' * 64, 'reviewed': True, 'passed_gate': True, 'aggregate_gain_vs_best_component': 0.01, 'slice_regressions': []}
        }]
        p.write_text(json.dumps(broken))
        try:
            validate(p)
        except ValueError:
            pass
        else:
            fail('self-test expected sub-threshold combination gain to fail')

        broken = json.loads(json.dumps(good))
        broken['combination_candidates'] = [{
            'id': 'bad-regression',
            'eligible_for_combination': True,
            'components': [
                {'repository': 'dtf/a', 'revision': 'a' * 40, 'promotion_report': {'path': 'a.json', 'sha256': 'b' * 64, 'reviewed': True, 'passed_gate': True}},
                {'repository': 'dtf/b', 'revision': 'c' * 40, 'promotion_report': {'path': 'b.json', 'sha256': 'd' * 64, 'reviewed': True, 'passed_gate': True}}
            ],
            'combination_report': {'path': 'combo.json', 'sha256': 'e' * 64, 'reviewed': True, 'passed_gate': True, 'aggregate_gain_vs_best_component': 0.03, 'slice_regressions': ['factuality']}
        }]
        p.write_text(json.dumps(broken))
        try:
            validate(p)
        except ValueError:
            pass
        else:
            fail('self-test expected protected slice regression to fail')


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
