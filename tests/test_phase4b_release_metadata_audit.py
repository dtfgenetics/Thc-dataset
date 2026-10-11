"""Offline metadata-auditor regressions; no GitHub API or archive bytes required."""
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "scripts" / "audit-phase4b-release-metadata.py"
spec = importlib.util.spec_from_file_location("phase4b_metadata", source)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture():
    manifest = {"results": []}
    assets = []
    for did in sorted(mod.DATASETS):
        name = did + "_archive.part001"
        digest = "a" * 64
        manifest["results"].append({"datasetId": did, "status": "acquired",
            "originalArchive": {"sizeBytes": 10, "sha256": digest}, "archiveParts": [
            {"filename": name, "partIndex": 1, "partCount": 1, "sizeBytes": 10, "sha256": digest}]})
        assets.append({"name": name, "size": 10, "state": "uploaded", "digest": "sha256:" + digest})
    return manifest, assets


class ReleaseMetadataAuditTests(unittest.TestCase):
    def test_complete_metadata_passes(self):
        manifest, assets = fixture()
        self.assertEqual(mod.audit(manifest, assets)["status"], "pass")

    def test_missing_archive_part_fails(self):
        manifest, assets = fixture()
        assets.pop()
        report = mod.audit(manifest, assets)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("Missing published part" in e for e in report["errors"]))

    def test_duplicate_asset_fails(self):
        manifest, assets = fixture()
        assets.append(dict(assets[0]))
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_wrong_digest_fails(self):
        manifest, assets = fixture()
        assets[0]["digest"] = "sha256:" + "b" * 64
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_wrong_size_fails(self):
        manifest, assets = fixture()
        assets[0]["size"] = 11
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_missing_dataset_fails(self):
        manifest, assets = fixture()
        manifest["results"].pop()
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_failed_acquisition_fails(self):
        manifest, assets = fixture()
        manifest["results"][0]["status"] = "failed"
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_original_archive_size_mismatch_fails(self):
        manifest, assets = fixture()
        manifest["results"][0]["originalArchive"]["sizeBytes"] = 11
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_asset_not_uploaded_fails(self):
        manifest, assets = fixture()
        assets[0]["state"] = "starter"
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_invalid_part_size_fails(self):
        manifest, assets = fixture()
        manifest["results"][0]["archiveParts"][0]["sizeBytes"] = 0
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_invalid_original_checksum_fails(self):
        manifest, assets = fixture()
        manifest["results"][0]["originalArchive"]["sha256"] = "bad"
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_empty_archive_parts_fails(self):
        manifest, assets = fixture()
        manifest["results"][0]["archiveParts"] = []
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_malformed_published_archive_name_fails(self):
        manifest, assets = fixture()
        assets.append({"name": "DS-142_archive.partBAD", "size": 10})
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")

    def test_undeclared_asset_fails(self):
        manifest, assets = fixture()
        assets.append({"name": "DS-142_archive.part002", "size": 10})
        self.assertEqual(mod.audit(manifest, assets)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
