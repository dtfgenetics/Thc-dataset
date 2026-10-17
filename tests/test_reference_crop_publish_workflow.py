#!/usr/bin/env python3
"""Exercise reference-crop publishing against concurrent Git changes.

Run: python tests/test_reference_crop_publish_workflow.py .github/workflows/build-reference-crops.yml
No network or third-party test runner required; uses disposable local Git repos.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import yaml

INPUTS = {
    'manifest': 'images/reference/manifest.json',
    'original': 'images/reference/original/original.txt',
    'crop-spec': 'data/reference-crop-spec.json',
    'grid-spec': 'data/reference-grid-crop-spec.json',
    'generator': 'scripts/build-reference-crops.py',
    'workflow': '.github/workflows/build-reference-crops.yml',
}
OUTPUTS = {
    'crop': 'images/reference/crops/a.txt',
    'crop-manifest': 'images/reference/crops-manifest.json',
}


def git(args, cwd, check=True):
    result = subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True)
    if check and result.returncode:
        raise AssertionError(f'git {args}: {result.returncode}: {result.stderr}')
    return result


def scenario(name, publisher):
    with tempfile.TemporaryDirectory(prefix='growdoc-race-') as tmp:
        root = Path(tmp)
        remote, seed, worker, other = [root / n for n in ('remote.git', 'seed', 'worker', 'other')]
        git(['init', '--bare', str(remote)], root)
        git(['clone', str(remote), str(seed)], root)
        git(['checkout', '-b', 'main'], seed)
        paths = {**{v: 'source' for v in INPUTS.values()}, **{v: 'old' for v in OUTPUTS.values()}, 'unrelated.txt': 'old'}
        for path, contents in paths.items():
            file = seed / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(contents)
        git(['add', '.'], seed)
        git(['-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-m', 'seed'], seed)
        git(['push', 'origin', 'main'], seed)
        git(['clone', '--branch', 'main', str(remote), str(worker)], root)
        git(['clone', '--branch', 'main', str(remote), str(other)], root)

        (worker / OUTPUTS['crop']).write_text('generated')
        (worker / OUTPUTS['crop-manifest']).write_text('generated')
        target = ('unrelated.txt' if name == 'unrelated' else
                  'images/reference/crops/other.txt' if name == 'new-crop' else
                  'images/reference/original/new-original.txt' if name == 'new-original' else
                  INPUTS.get(name, OUTPUTS.get(name)))
        assert target, name
        (other / target).parent.mkdir(parents=True, exist_ok=True)
        (other / target).write_text('concurrent')
        git(['add', '.'], other)
        git(['-c', 'user.name=Other', '-c', 'user.email=other@example.com', 'commit', '-m', 'concurrent'], other)
        git(['push', 'origin', 'main'], other)

        result = subprocess.run(['bash', '-e', '-c', publisher], cwd=worker, text=True, capture_output=True)
        git(['fetch', 'origin', 'main'], seed)
        crop = git(['show', f'origin/main:{OUTPUTS["crop"]}'], seed).stdout.strip()
        crop_manifest = git(['show', f'origin/main:{OUTPUTS["crop-manifest"]}'], seed).stdout.strip()
        if name == 'unrelated':
            assert result.returncode == 0 and crop == 'generated' and crop_manifest == 'generated', (name, result.stderr)
        else:
            assert result.returncode != 0 and crop != 'generated' and crop_manifest != 'generated', (name, result.stderr)
            assert '::error::' in result.stdout or '::error::' in result.stderr, (name, result.stdout, result.stderr)
        print(f'PASS {name}: exit={result.returncode}, crop={crop}, manifest={crop_manifest}')


def main():
    path = Path(sys.argv[1])
    workflow = yaml.safe_load(path.read_text())
    triggers = workflow.get('on', workflow.get(True))
    assert 'images/reference/original/**' in triggers['push']['paths']
    assert 'images/reference/original/**' in triggers['pull_request']['paths']
    steps = workflow['jobs']['build-crops']['steps']
    commit_step = next(s for s in steps if s.get('name') == 'Commit validated crops')
    assert "github.event_name != 'pull_request'" in commit_step['if']
    assert "github.ref == 'refs/heads/main'" in commit_step['if']
    checkout = next(s for s in steps if s.get('uses', '').startswith('actions/checkout@'))
    assert checkout.get('with', {}).get('fetch-depth') == 0
    publisher = commit_step['run']
    for step in steps:
        if 'run' in step:
            syntax = subprocess.run(['bash', '-n'], input=step['run'], text=True, capture_output=True)
            assert syntax.returncode == 0, (step['name'], syntax.stderr)
    assert any(s.get('name') == 'Upload crop evidence artifact' and 'always()' in s.get('if', '') for s in steps)
    print('PASS workflow: YAML, Bash syntax, original-image triggers, artifact preservation')
    for name in ('unrelated', 'new-crop', 'new-original', *INPUTS.keys(), *OUTPUTS.keys()):
        scenario(name, publisher)


if __name__ == '__main__':
    main()
