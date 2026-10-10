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

    def test_missing_state_is_rejected(self):
        self.assets[0].pop("state")
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["verifiedParts"], 2)

    def test_unknown_state_is_rejected(self):
        self.assets[0]["state"] = "pending"
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_release_asset_size_must_be_positive_integer(self):
        for invalid in (True, False, "6", 6.0, None, -1, 0):
            with self.subTest(size=invalid):
                original = self.assets[0]["size"]
                self.assets[0]["size"] = invalid
                report = mod.validate(self.manifest, self.assets, self.root)
                self.assertEqual(report["status"], "fail")
                self.assertTrue(any("Release asset size mismatch" in error for error in report["errors"]))
                self.assets[0]["size"] = original

    def test_missing_asset(self):
        self.assertEqual(mod.validate(self.manifest, self.assets[:-1], self.root)["status"], "fail")

    def test_digest_mismatch(self):
        self.assets[0]["digest"] = "sha256:" + "0" * 64
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_missing_digest(self):
        self.assets[0].pop("digest")
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_nonconsecutive_archive_parts_fail_closed(self):
        part = self.rows[0]["archiveParts"][0]
        old_name = part["filename"]
        new_name = old_name.replace("part001", "part002")
        (self.root / old_name).rename(self.root / new_name)
        part["filename"] = new_name
        self.assets[0]["name"] = new_name
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("part sequence has gaps" in error for error in report["errors"]))

    def test_duplicate_declared_archive_part_fails_closed(self):
        self.rows[0]["archiveParts"].append(dict(self.rows[0]["archiveParts"][0]))
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("Duplicate declared part" in error for error in report["errors"]))

    def test_missing_manifest_checksum_fails_closed(self):
        self.rows[0]["archiveParts"][0].pop("sha256")
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("Local checksum/size differs" in error for error in report["errors"]))

    def test_duplicate_release_asset_name_fails_closed(self):
        self.assets.append(dict(self.assets[0]))
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("Duplicate release asset" in error for error in report["errors"]))

    def test_missing_chunk(self):
        (self.root / self.assets[0]["name"]).unlink()
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_incomplete_acquisition(self):
        self.rows[0]["status"] = "blocked"
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_malformed_archive_part_fails_closed(self):
        self.rows[0]["archiveParts"].append(None)
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("malformed archive part" in e for e in report["errors"]))

    def test_malformed_release_asset_fails_closed(self):
        report = mod.validate(self.manifest, self.assets + [None], self.root)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("Malformed release asset" in e for e in report["errors"]))

    def test_non_object_manifest_fails_closed(self):
        report = mod.validate([], self.assets, self.root)
        self.assertEqual(report["status"], "fail")

    def test_non_list_release_assets_fails_closed(self):
        report = mod.validate(self.manifest, None, self.root)
        self.assertEqual(report["status"], "fail")

    def test_non_string_dataset_id_fails_closed(self):
        self.rows[0]["datasetId"] = None
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")

    def test_unhashable_dataset_id_fails_closed(self):
        self.rows[0]["datasetId"] = ["DS-142"]
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_unicode_digit_suffix_fails_closed(self):
        self.rows[0]["archiveParts"][0]["filename"] = "DS-142_archive.part00\u0661"
        self.assertEqual(mod.validate(self.manifest, self.assets, self.root)["status"], "fail")

    def test_undeclared_release_archive_part_fails(self):
        self.assets.append({"name": "DS-142_archive.part099", "size": 5, "digest": "sha256:" + "0" * 64, "state": "uploaded"})
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("Undeclared release archive assets" in e for e in report["errors"]))

    def test_extra_characters_before_part_suffix_fail_closed(self):
        self.rows[0]["archiveParts"][0]["filename"] = "DS-142_archive.part-extra001"
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("invalid filename" in error for error in report["errors"]))

    def test_nonpositive_or_noninteger_chunk_size_fails_closed(self):
        for invalid in (0, -1, True, False, "5", 5.0, None):
            with self.subTest(size=invalid):
                self.rows[0]["archiveParts"][0]["sizeBytes"] = invalid
                report = mod.validate(self.manifest, self.assets, self.root)
                self.assertEqual(report["status"], "fail")
                self.assertTrue(any("invalid non-positive archive part size" in e for e in report["errors"]))

    def test_zero_byte_chunk_with_matching_sha_and_asset_fails_closed(self):
        part = self.rows[0]["archiveParts"][0]
        name = part["filename"]
        (self.root / name).write_bytes(b"")
        digest = hashlib.sha256(b"").hexdigest()
        part.update(sizeBytes=0, sha256=digest)
        self.assets[0].update(size=0, digest="sha256:" + digest)
        report = mod.validate(self.manifest, self.assets, self.root)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("invalid non-positive archive part size" in e for e in report["errors"]))

if __name__ == "__main__":
    unittest.main()
