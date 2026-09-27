#!/usr/bin/env python3
"""Stable validation entrypoint for the Grow Doc near-duplicate audit."""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDITOR = ROOT / "scripts" / "audit-grow-doc-near-duplicates.py"
TESTS = ROOT / "tests"


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main() -> int:
    run("-m", "py_compile", str(AUDITOR))
    run(str(AUDITOR), "--self-test")
    run("-m", "unittest", "discover", "-s", str(TESTS), "-p", "test_grow_doc_near_duplicate_audit.py", "-v")
    print("Grow Doc near-duplicate validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
