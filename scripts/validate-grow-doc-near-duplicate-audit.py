#!/usr/bin/env python3
"""Compatibility entrypoint; delegates to the canonical validation runner."""
from __future__ import annotations

import pathlib
import runpy

ROOT = pathlib.Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "scripts" / "run-grow-doc-near-duplicate-validation.py"), run_name="__main__")
