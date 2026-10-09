"""Exercise the release publisher's starter-asset safety behavior with a fake gh CLI."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLISH = ROOT / "scripts" / "publish-release-chunks-idempotent.sh"

FAKE_GH = """#!/usr/bin/env python3
import os, sys
from pathlib import Path
args = sys.argv[1:]
log = Path(os.environ["GH_MOCK_LOG"])
with log.open("a") as fp:
    fp.write(" ".join(args) + "\\n")
if args[:2] == ["api", "repos/example/repo/releases/tags/demo"]:
    print("101")
elif args[:2] == ["api", "--paginate"]:
    print("41\\tDS-142_archive.part001\\t0\\t-\\tstarter")
elif args[:2] == ["api", "repos/example/repo/releases/assets/41"]:
    state = os.environ.get("GH_MOCK_REFETCH_STATE", "starter")
    size = int(os.environ.get("GH_MOCK_REFETCH_SIZE", "0" if state == "starter" else "4"))
    print(f"DS-142_archive.part001\\t{size}\\t-\\t{state}")
elif args[:3] == ["api", "-X", "DELETE"]:
    pass
elif args[:2] == ["release", "upload"]:
    pass
else:
    raise SystemExit("Unexpected gh request " + repr(args))
"""

class StarterRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.asset = root / "DS-142_archive.part001"
        self.asset.write_bytes(b"test")
        (root / "gh").write_text(FAKE_GH)
        (root / "gh").chmod(0o755)
        self.log = root / "calls.txt"
        self.env = os.environ.copy()
        self.env.update(GITHUB_REPOSITORY="example/repo",
                        GH_MOCK_LOG=str(self.log),
                        PATH=str(root) + os.pathsep + self.env["PATH"])

    def run_publish(self, repair=False, changed=False):
        env = dict(self.env)
        env["THC_REPAIR_STARTER_ASSETS"] = "1" if repair else "0"
        if changed:
            env["GH_MOCK_REFETCH_STATE"] = "uploaded"
        result = subprocess.run(["bash", str(PUBLISH), "demo", str(self.asset)],
                                env=env, capture_output=True, text=True)
        return result, self.log.read_text()

    def test_fails_closed_by_default(self):
        result, calls = self.run_publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("DELETE", calls)
        self.assertNotIn("release upload", calls)

    def test_opt_in_repairs_only_zero_byte_starter(self):
        result, calls = self.run_publish(repair=True)
        self.assertEqual(result.returncode, 0, result.stderr + "\nMock calls:\n" + calls)
        self.assertIn("DELETE", calls)
        self.assertIn("release upload", calls)

    def test_repair_accepts_expected_size_starter(self):
        env = dict(self.env)
        env["THC_REPAIR_STARTER_ASSETS"] = "1"
        env["GH_MOCK_REFETCH_SIZE"] = "4"
        result = subprocess.run(["bash", str(PUBLISH), "demo", str(self.asset)],
                                env=env, capture_output=True, text=True)
        calls = self.log.read_text()
        self.assertEqual(result.returncode, 0, result.stderr + "\\n" + calls)
        self.assertIn("DELETE", calls)

    def test_refuses_asset_changed_during_repair(self):
        result, calls = self.run_publish(repair=True, changed=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("DELETE", calls)
        self.assertNotIn("release upload", calls)

if __name__ == "__main__":
    unittest.main()
