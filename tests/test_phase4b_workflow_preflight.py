"""Regression tests for the real Phase 4B inline preflight."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/bulk-transfer-phase4b.yml"

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.directory = self.root / "bulk_acquisition/phase4b_public"
        self.directory.mkdir(parents=True)
        self.rows = []
        for dataset in ("DS-142", "DS-143", "DS-146"):
            name = dataset + "_archive.part001"
            payload = dataset.encode()
            (self.directory / name).write_bytes(payload)
            self.rows.append({"datasetId": dataset, "status": "acquired", "archiveParts": [{
                "filename": name, "sizeBytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()
            }]})

    def run_preflight(self):
        workflow = WORKFLOW.read_text()
        marker = "          python - <<'PY'\n"
        self.assertEqual(workflow.count(marker), 1)
        script = textwrap.dedent(workflow.split(marker, 1)[1].split("\n          PY", 1)[0])
        (self.directory / "phase4b-manifest.json").write_text(json.dumps({"results": self.rows}))
        return subprocess.run([sys.executable, "-c", script], cwd=self.root, capture_output=True, text=True)

    def assert_rejected(self):
        result = self.run_preflight()
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_valid(self):
        result = self.run_preflight()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_duplicate_dataset(self):
        self.rows[1]["datasetId"] = "DS-142"
        self.assert_rejected()

    def test_non_object_dataset(self):
        self.rows[0] = None
        self.assert_rejected()

    def test_non_list_parts(self):
        self.rows[0]["archiveParts"] = {}
        self.assert_rejected()

    def test_non_object_part(self):
        self.rows[0]["archiveParts"] = [None]
        self.assert_rejected()

    def test_invalid_sizes(self):
        for value in (0, -1, True, False, "6", 6.0, None):
            with self.subTest(value=value):
                self.rows[0]["archiveParts"][0]["sizeBytes"] = value
                self.assert_rejected()

    def test_checksum_mismatch(self):
        self.rows[0]["archiveParts"][0]["sha256"] = "0" * 64
        self.assert_rejected()

    def test_undeclared_part(self):
        (self.directory / "DS-142_archive.part002").write_bytes(b"extra")
        self.assert_rejected()

if __name__ == "__main__":
    unittest.main()
