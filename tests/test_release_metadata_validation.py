"""Exercise the real release validator against isolated, mutated JSON artifacts."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    'data/manifest.json', 'data/profiles/index.json', 'data/sources.json',
    'data/profile-reference-media.json', 'data/training-eligible-media.json',
    'data/model-training-readiness.json', 'data/splits/manifest.json',
    'images/reference/manifest.json', 'images/reference/crops-manifest.json',
    'data/profile-materialization-status.json',
    'data/export-manifest.json',
]


class ReleaseMetadataValidationTests(unittest.TestCase):
    def run_validator(self, mutation=None):
        docs = {path: json.loads((ROOT / path).read_text()) for path in FILES}
        manifest = docs['data/manifest.json']
        originals = docs['images/reference/manifest.json']['recordCount']
        crops = docs['images/reference/crops-manifest.json']['recordCount']
        profiles = docs['data/profiles/index.json']['recordCount']
        manifest['releaseStatus'] = f'{profiles}-profile-release-validated'
        manifest['measuredReleaseCounts'] = {
            'diagnosticProfiles': profiles,
            'coreProfiles': docs['data/export-manifest.json']['counts']['primaryDiagnosticProfiles'],
            'supplementalAndExpandedProfiles': docs['data/export-manifest.json']['counts']['supplementalDiagnosticProfiles'],
            'uniqueEvidenceSources': len(docs['data/sources.json']),
            'profileLinkedMedia': len(docs['data/profile-reference-media.json']),
            'referenceOriginals': originals, 'referenceCrops': crops,
            'totalReferenceImages': originals + crops,
            'trainingEligibleMedia': len(docs['data/training-eligible-media.json']),
        }
        docs['data/profile-materialization-status.json']['scope'] = 'historical-release-verification'
        if mutation:
            mutation(docs)
        with tempfile.TemporaryDirectory() as directory:
            for path, doc in docs.items():
                dest = Path(directory) / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(doc))
            return subprocess.run(['node', str(ROOT / 'scripts/validate-release-metadata.mjs')],
                                  cwd=directory, text=True, capture_output=True)

    def test_valid_current_counts_allow_scoped_historical_counts(self):
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stale_source_summary_is_rejected(self):
        result = self.run_validator(lambda d: d['data/manifest.json']['measuredReleaseCounts'].update(uniqueEvidenceSources=1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('measuredReleaseCounts.uniqueEvidenceSources', result.stderr)

    def test_stale_media_summary_is_rejected(self):
        result = self.run_validator(lambda d: d['data/manifest.json']['measuredReleaseCounts'].update(profileLinkedMedia=1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('measuredReleaseCounts.profileLinkedMedia', result.stderr)

    def test_stale_original_summary_is_rejected(self):
        result = self.run_validator(lambda d: d['data/manifest.json']['measuredReleaseCounts'].update(referenceOriginals=1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('measuredReleaseCounts.referenceOriginals', result.stderr)

    def test_stale_total_summary_is_rejected(self):
        result = self.run_validator(lambda d: d['data/manifest.json']['measuredReleaseCounts'].update(totalReferenceImages=1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('measuredReleaseCounts.totalReferenceImages', result.stderr)

    def test_historical_materialization_must_be_scoped(self):
        result = self.run_validator(lambda d: d['data/profile-materialization-status.json'].pop('scope'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('materialization.scope', result.stderr)

    def test_stale_profile_release_label_is_rejected(self):
        result = self.run_validator(lambda d: d['data/manifest.json'].update(releaseStatus='61-profile-release-validated'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('manifest.releaseStatus', result.stderr)


if __name__ == '__main__':
    unittest.main()
