#!/usr/bin/env python3
"""Materialize and hash the exact Grow Doc training/retrieval artifact set.

This is a data-freeze utility only. It does not run training, inference, adapter
merging, model soup, or deployment. The generated lock records byte-level hashes
for the split manifest and leak-safe training-dataset manifest so a later real
QLoRA run can bind to immutable inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "model_tuning/generated"
HELDOUT = ROOT / "model_tuning/eval/heldout_v2.jsonl"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def freeze(out: pathlib.Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    run("scripts/build-model-corpus.py", "--out", str(out))
    run("scripts/split-model-sft.py", "--out", str(out / "splits"))

    split_manifest = out / "splits/split_manifest_v1.json"
    training_manifest = out / "training_dataset_manifest_v2.json"
    run(
        "scripts/build-training-dataset-manifest.py",
        "--train-sft", str(out / "splits/train_sft_v1.jsonl"),
        "--dev-sft", str(out / "splits/dev_sft_v1.jsonl"),
        "--train-grounded-qa", str(out / "splits/train_grounded_qa_v1.jsonl"),
        "--dev-grounded-qa", str(out / "splits/dev_grounded_qa_v1.jsonl"),
        "--retrieval", str(out / "rag/claims_v1.jsonl"),
        "--quarantine", str(out / "quarantine/quarantine_v1.jsonl"),
        "--heldout", str(HELDOUT),
        "--split-manifest", str(split_manifest),
        "--output", str(training_manifest),
    )

    training = json.loads(training_manifest.read_text(encoding="utf-8"))
    split = json.loads(split_manifest.read_text(encoding="utf-8"))
    corpus = json.loads((out / "manifest_v1.json").read_text(encoding="utf-8"))
    lock = {
        "schema_version": "grow-doc-training-artifact-lock-v1",
        "policy": "byte-level freeze of leak-safe training, retrieval, quarantine, split, and heldout provenance; no model run implied",
        "heldout_path": "model_tuning/eval/heldout_v2.jsonl",
        "heldout_sha256": sha256(HELDOUT),
        "corpus_manifest_path": "model_tuning/generated/manifest_v1.json",
        "corpus_manifest_sha256": sha256(out / "manifest_v1.json"),
        "split_manifest_path": "model_tuning/generated/splits/split_manifest_v1.json",
        "split_manifest_sha256": sha256(split_manifest),
        "training_dataset_manifest_path": "model_tuning/generated/training_dataset_manifest_v2.json",
        "training_dataset_manifest_sha256": sha256(training_manifest),
        "training_dataset_manifest_internal_sha256": training.get("manifest_sha256"),
        "split_algorithm": split.get("algorithm"),
        "split_seed": split.get("seed"),
        "input_sha256": corpus.get("input_sha256"),
        "eval_sha256": corpus.get("eval_sha256"),
        "training_rows": (training.get("mixture") or {}).get("training_rows"),
        "grounded_qa_fraction": (training.get("mixture") or {}).get("grounded_qa_fraction"),
    }
    (out / "training_artifact_lock_v1.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return lock


def self_test() -> None:
    required = {
        "build-model-corpus.py",
        "split-model-sft.py",
        "build-training-dataset-manifest.py",
    }
    present = {p.name for p in (ROOT / "scripts").iterdir() if p.is_file()}
    missing = sorted(required - present)
    if missing:
        raise AssertionError(f"missing freezer dependencies: {missing}")
    print("training artifact freezer self-test: PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        lock = freeze(args.out)
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"training artifact freeze: FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(lock, sort_keys=True))
    print("training artifact freeze: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
