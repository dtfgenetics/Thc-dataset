#!/usr/bin/env python3
"""Canonical validation runner for Grow Doc near-duplicate auditing."""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDITOR = ROOT / "scripts" / "audit-grow-doc-near-duplicates.py"
TESTS = ROOT / "tests"

commands = [
    [sys.executable, "-m", "py_compile", str(AUDITOR)],
    [sys.executable, str(AUDITOR), "--self-test"],
    [sys.executable, "-m", "unittest", "discover", "-s", str(TESTS), "-p", "test_grow_doc_near_duplicate_audit.py", "-v"],
]
for command in commands:
    subprocess.run(command, cwd=ROOT, check=True)
print("Grow Doc near-duplicate validation: PASS")
