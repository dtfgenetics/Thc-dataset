"""Offline acceptance tests: no GitHub release access required."""
import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify-phase4b-release.py"
spec = importlib.util.spec_from_file_location("phase4b_acceptance", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ReleaseAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = []
        self.assets = []
        for did in sorted(mod.EXPECTED):
            name = f"{did}_archive.part001"
            content = did.encode()
            (self.root / name).write_bytes(content)
            sha = hashlib.sha256(content).hexdigest()
            self.rows.append({"datasetId": did, "status": "acquired", "archiveParts": [
                {"filename": name, "sizeBytes": len(content), "sha256": sha}
            ]})
            self.assets.append({"name": name, "size": len(content), "digest": "sha256:" + sha, "state": "uploaded"})
        self.manifest = {"results": self.rows}

    def test_pass(self):
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "pass")

    def test_starter_asset_with_matching_size_and_digest_is_rejected(self):
        self.assets[0]["state"] = "starter"
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_uploaded_asset_with_matching_size_and_digest_passes(self):
        for asset in self.assets:
            asset["state"] = "uploaded"
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "pass")

    def test_missing_asset(self):
        self.assertEqual(mod.validate(self.manifest, self.assets[:-1], self.root)["status"], "fail")

    def test_digest_mismatch(self):
        self.assets[0]["digest"] = "sha256:" + "0" * 64
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_missing_digest(self):
        self.assets[0].pop("digest")
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_missing_chunk(self):
        (self.root / self.assets[0]["name"]).unlink()
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_incomplete_acquisition(self):
        self.rows[0]["status"] = "blocked"
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

if __name__ == "__main__":
    unittest.main()
