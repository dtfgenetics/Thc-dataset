#!/usr/bin/env python3
"""Regression tests for the acquisition archive verifier."""
from __future__ import annotations
import copy
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify-acquisition-artifacts.py"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

class VerifyAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "part-01.tar"
        with tarfile.open(self.archive, "w") as tf:
            data = b"test-image"
            info = tarfile.TarInfo("plant/leaf.jpg")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        self.manifest = {
            "schemaVersion": "1.0.0",
            "datasetId": "test-case",
            "sourceUrl": "https://example.org/dataset",
            "sourceRevision": "test-rev",
            "license": "test-license",
            "shardCount": 1,
            "totalFiles": 1,
            "totalImages": 1,
            "totalArchiveBytes": self.archive.stat().st_size,
            "shards": [{
                "fileName": self.archive.name,
                "sha256": sha256(self.archive),
                "bytes": self.archive.stat().st_size,
                "fileCount": 1,
                "imageCount": 1
            }]
        }
        self.manifest_path = self.root / "manifest.json"

    def run_check(self, expected: int):
        self.manifest_path.write_text(json.dumps(self.manifest))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.manifest_path)],
            text=True, capture_output=True, check=False
        )
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)["results"][0]

    def test_valid_shard(self):
        self.assertEqual(self.run_check(0)["images"], 1)

    def test_archive_tamper(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"tampering")
        result = self.run_check(1)
        self.assertTrue(any("SHA256 mismatch" in x for x in result["errors"]))

    def test_missing_archive(self):
        self.archive.unlink()
        result = self.run_check(1)
        self.assertTrue(any("Missing shard" in x for x in result["errors"]))

    def test_duplicate_archive_name(self):
        self.manifest["shards"].append(copy.deepcopy(self.manifest["shards"][0]))
        result = self.run_check(1)
        self.assertTrue(any("Duplicate shard" in x for x in result["errors"]))

    def test_unsafe_tar_entry(self):
        with tarfile.open(self.archive, "w") as tf:
            data = b"test-image"
            info = tarfile.TarInfo("../leaf.jpg")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        self.manifest["shards"][0].update({
            "sha256": sha256(self.archive),
            "bytes": self.archive.stat().st_size
        })
        self.manifest["totalArchiveBytes"] = self.archive.stat().st_size
        result = self.run_check(1)
        self.assertTrue(any("Unsafe archive member" in x for x in result["errors"]))

    def test_missing_provenance(self):
        self.manifest["sourceRevision"] = ""
        result = self.run_check(1)
        self.assertTrue(any("Missing provenance field" in x for x in result["errors"]))

    def test_unlisted_tar(self):
        (self.root / "extra.tar").write_bytes(self.archive.read_bytes())
        result = self.run_check(1)
        self.assertTrue(any("Unlisted tar shards" in x for x in result["errors"]))

    def test_duplicate_tar_member_path(self):
        with tarfile.open(self.archive, "w") as tf:
            for _ in range(2):
                data = b"test-image"
                info = tarfile.TarInfo("plant/leaf.jpg")
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        self.manifest["shards"][0].update({
            "sha256": sha256(self.archive),
            "bytes": self.archive.stat().st_size,
            "fileCount": 2,
            "imageCount": 2
        })
        self.manifest["totalFiles"] = 2
        self.manifest["totalImages"] = 2
        self.manifest["totalArchiveBytes"] = self.archive.stat().st_size
        result = self.run_check(1)
        self.assertTrue(any("Duplicate archive member path" in x for x in result["errors"]))

    def test_no_images(self):
        self.manifest["totalImages"] = 0
        result = self.run_check(1)
        self.assertTrue(any("totalImages mismatch" in x for x in result["errors"]))

if __name__ == "__main__":
    unittest.main()
