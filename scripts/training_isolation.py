#!/usr/bin/env python3
"""Shared training-isolation path policy for frozen Grow Doc benchmarks.

The active benchmark may change, but sources/prompts that were frozen in an older promotion
benchmark must never silently become weight-training data after a benchmark migration.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEGACY_TRAINING_HOLDOUTS = (
    ROOT / "model_tuning/eval/heldout_v2.jsonl",
)


def training_isolation_paths(active_eval: pathlib.Path, default_active_eval: pathlib.Path) -> list[pathlib.Path]:
    paths = [active_eval]
    if active_eval.resolve() == default_active_eval.resolve():
        for legacy in LEGACY_TRAINING_HOLDOUTS:
            if legacy.exists() and legacy.resolve() != active_eval.resolve():
                paths.append(legacy)
    return paths


def display_repo_path(path: pathlib.Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)
