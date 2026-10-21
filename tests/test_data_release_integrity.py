"""Mutate isolated exports and Git fixtures; never touch canonical artifacts."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DataReleaseIntegrityTests(unittest.TestCase):
    def validate(self, mutate=None):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            shutil.copytree(ROOT / 'data', target / 'data')
            (target / 'images').symlink_to(ROOT / 'images', target_is_directory=True)
            if mutate:
                mutate(target)
            return subprocess.run(['node', str(ROOT / 'scripts/validate-data-release.mjs')],
                                  cwd=target, capture_output=True, text=True)

    def test_current_release_passes_without_regeneration(self):
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_jsonl_content_change_preserving_ids_is_rejected(self):
        def mutate(target):
            file = target / 'data/diagnostic-profiles.jsonl'
            records = [json.loads(line) for line in file.read_text().splitlines()]
            records[0]['summary'] = 'Altered content with the same identifier'
            file.write_text('\n'.join(json.dumps(row) for row in records) + '\n')
        result = self.validate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('content differs from diagnostic-profiles.json', result.stderr)

    def test_jsonl_record_reordering_is_rejected(self):
        def mutate(target):
            file = target / 'data/diagnostic-profiles.jsonl'
            rows = file.read_text().splitlines()
            rows[0], rows[1] = rows[1], rows[0]
            file.write_text('\n'.join(rows) + '\n')
        result = self.validate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('content differs from diagnostic-profiles.json', result.stderr)

    def test_omitted_eligible_record_is_rejected(self):
        def mutate(target):
            file = target / 'data/profile-reference-media.json'
            rows = json.loads(file.read_text())
            rows[0].update(trainingEligible=True, trainingPermission='permitted')
            file.write_text(json.dumps(rows))
        result = self.validate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exported subset differs', result.stderr)

    def test_altered_eligible_provenance_is_rejected(self):
        def mutate(target):
            source = target / 'data/profile-reference-media.json'
            rows = json.loads(source.read_text())
            rows[0].update(trainingEligible=True, trainingPermission='permitted')
            source.write_text(json.dumps(rows))
            eligible = dict(rows[0], sourceUrl='https://example.invalid/changed-provenance')
            (target / 'data/training-eligible-media.json').write_text(json.dumps([eligible]))
        result = self.validate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exported subset differs', result.stderr)

    def test_actual_workflow_guards_reject_tracked_untracked_and_deleted_outputs(self):
        for workflow in ['export-machine-data.yml', 'validate-data-release.yml']:
            text = (ROOT / '.github/workflows' / workflow).read_text()
            self.assertIn("ref: ${{ github.event.pull_request.head.sha || github.sha }}", text)
            step = text.split('- name: Reject generated export drift on pull requests\n', 1)[1]
            self.assertIn("if: github.event_name == 'pull_request'", step.split('run: |', 1)[0])
            lines = step.split('run: |\n', 1)[1].splitlines()
            body = []
            for line in lines:
                if line.strip() and not line.startswith('          '):
                    break
                body.append(line[10:] if line.strip() else '')
            command = '\n'.join(body)
            for state in ['clean', 'modified', 'untracked', 'deleted', 'unrelated']:
                with self.subTest(workflow=workflow, state=state), tempfile.TemporaryDirectory() as directory:
                    target = Path(directory)
                    (target / 'data').mkdir()
                    file = target / 'data/export.json'
                    file.write_text('{}\n')
                    def git(*args):
                        return subprocess.run(['git', *args], cwd=target, check=True, capture_output=True)
                    git('init', '-q')
                    git('add', 'data')
                    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
                    if state == 'modified': file.write_text('{"changed":true}\n')
                    if state == 'untracked': (target / 'data/new.json').write_text('{}\n')
                    if state == 'deleted': file.unlink()
                    if state == 'unrelated': (target / 'unrelated.txt').write_text('outside data\n')
                    result = subprocess.run(['bash', '-ec', command], cwd=target, capture_output=True, text=True)
                    self.assertEqual(result.returncode == 0, state in ['clean', 'unrelated'], result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
