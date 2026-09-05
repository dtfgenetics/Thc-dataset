#!/usr/bin/env python3
"""Materialize and hash the exact Grow Doc training/retrieval artifact set.

This is a data-freeze utility only. It does not run training, inference, adapter
merging, model soup, or deployment. The generated lock records byte-level hashes
for the source split, capped training mixture split, and leak-safe training-dataset
manifest so a later real QLoRA run can bind to immutable inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import shutil
import subprocess
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "model_tuning/generated"
HELDOUT = ROOT / "model_tuning/eval/heldout_v2.jsonl"
MIXTURE_VERSION = "grounded-qa-balanced-v1"
MIXTURE_SEED = 420
MAX_GROUNDED_QA_FRACTION = 0.20


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        rows.append(value)
    return rows


def write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def grounded_qa_limit(sft_rows: int, max_fraction: float = MAX_GROUNDED_QA_FRACTION) -> int:
    if sft_rows <= 0:
        raise ValueError("SFT training lane is empty")
    if not 0 < max_fraction < 1:
        raise ValueError("grounded-QA max fraction must be between 0 and 1")
    return math.floor((max_fraction * sft_rows) / (1.0 - max_fraction) + 1e-12)


def select_grounded_qa(rows: list[dict], limit: int, *, seed: int = MIXTURE_SEED) -> list[dict]:
    """Select a deterministic, profile-balanced subset without changing row content."""
    if limit < 0:
        raise ValueError("grounded-QA selection limit cannot be negative")
    seen = set()
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rid = row.get("id")
        profile_id = row.get("profile_id")
        if not rid or rid in seen:
            raise ValueError(f"duplicate or missing grounded-QA record id: {rid!r}")
        if not profile_id:
            raise ValueError(f"{rid}: profile_id is required for balanced selection")
        seen.add(rid)
        groups[str(profile_id)].append(row)
    if len(rows) <= limit:
        return sorted(rows, key=lambda row: row["id"])

    ordered_profiles = sorted(
        groups,
        key=lambda profile: stable_hash(f"{MIXTURE_VERSION}|{seed}|profile|{profile}"),
    )
    for profile in ordered_profiles:
        groups[profile].sort(
            key=lambda row: stable_hash(f"{MIXTURE_VERSION}|{seed}|record|{row['id']}")
        )

    selected: list[dict] = []
    depth = 0
    while len(selected) < limit:
        added = False
        for profile in ordered_profiles:
            bucket = groups[profile]
            if depth < len(bucket):
                selected.append(bucket[depth])
                added = True
                if len(selected) == limit:
                    break
        if not added:
            break
        depth += 1
    if len(selected) != limit:
        raise ValueError(f"unable to select requested grounded-QA rows: wanted {limit}, got {len(selected)}")
    return sorted(selected, key=lambda row: row["id"])


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def freeze(out: pathlib.Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    # Raw corpus builders remain research/candidate generators. The training split
    # is materialized only after strict supplied-claim grounding is enforced.
    run("scripts/build-model-corpus.py", "--out", str(out))
    run("scripts/split-model-training-grounded.py", "--out", str(out / "splits"))

    source_split_manifest = out / "splits/split_manifest_v1.json"
    source_train_qa = out / "splits/train_grounded_qa_v1.jsonl"
    train_sft = out / "splits/train_sft_v1.jsonl"
    selected_train_qa = out / "splits/train_grounded_qa_mixture_v1.jsonl"
    training_split_manifest = out / "splits/training_split_manifest_v1.json"
    training_manifest = out / "training_dataset_manifest_v2.json"

    sft_rows = load_jsonl(train_sft)
    qa_candidates = load_jsonl(source_train_qa)
    for row in sft_rows + qa_candidates:
        if row.get("grounding_mode") != "supplied_claims_only_v1":
            raise ValueError(f"{row.get('id')}: unsanitized record reached training freeze")
        if not row.get("evidence_claims"):
            raise ValueError(f"{row.get('id')}: evidence_claims missing at training freeze")

    qa_limit = grounded_qa_limit(len(sft_rows))
    qa_selected = select_grounded_qa(qa_candidates, min(qa_limit, len(qa_candidates)))
    write_jsonl(selected_train_qa, qa_selected)

    mixture_fraction = len(qa_selected) / (len(sft_rows) + len(qa_selected))
    if mixture_fraction > MAX_GROUNDED_QA_FRACTION + 1e-12:
        raise ValueError(
            f"selected grounded-QA fraction {mixture_fraction:.6f} exceeds cap {MAX_GROUNDED_QA_FRACTION:.6f}"
        )

    source_split = json.loads(source_split_manifest.read_text(encoding="utf-8"))
    training_split = dict(source_split)
    training_split["schema_version"] = "grow-doc-training-mixture-split-v2"
    training_split["grounding_policy"] = "supplied_claims_only_v1"
    training_split["parent_split_manifest_path"] = "model_tuning/generated/splits/split_manifest_v1.json"
    training_split["parent_split_manifest_sha256"] = sha256(source_split_manifest)
    training_split["train_grounded_qa_candidate_records"] = len(qa_candidates)
    training_split["train_grounded_qa_candidate_sha256"] = sha256(source_train_qa)
    training_split["train_grounded_qa_records"] = len(qa_selected)
    training_split["train_grounded_qa_sha256"] = sha256(selected_train_qa)
    training_split["train_records"] = len(sft_rows) + len(qa_selected)
    training_split["grounded_qa_selection"] = {
        "algorithm": MIXTURE_VERSION,
        "seed": MIXTURE_SEED,
        "max_fraction": MAX_GROUNDED_QA_FRACTION,
        "candidate_records": len(qa_candidates),
        "selected_records": len(qa_selected),
        "selected_fraction": round(mixture_fraction, 12),
        "profile_balanced_round_robin": True,
        "row_content_modified": False,
    }
    training_split_manifest.write_text(
        json.dumps(training_split, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    run(
        "scripts/build-training-dataset-manifest.py",
        "--train-sft", str(train_sft),
        "--dev-sft", str(out / "splits/dev_sft_v1.jsonl"),
        "--train-grounded-qa", str(selected_train_qa),
        "--dev-grounded-qa", str(out / "splits/dev_grounded_qa_v1.jsonl"),
        "--retrieval", str(out / "rag/claims_v1.jsonl"),
        "--quarantine", str(out / "quarantine/quarantine_v1.jsonl"),
        "--heldout", str(HELDOUT),
        "--split-manifest", str(training_split_manifest),
        "--output", str(training_manifest),
    )

    training = json.loads(training_manifest.read_text(encoding="utf-8"))
    corpus = json.loads((out / "manifest_v1.json").read_text(encoding="utf-8"))
    lock = {
        "schema_version": "grow-doc-training-artifact-lock-v3",
        "policy": "byte-level freeze of supplied-claim-grounded leak-safe split, capped training mixture, retrieval, quarantine, and heldout provenance; no model run implied",
        "grounding_policy": "supplied_claims_only_v1",
        "heldout_path": "model_tuning/eval/heldout_v2.jsonl",
        "heldout_sha256": sha256(HELDOUT),
        "corpus_manifest_path": "model_tuning/generated/manifest_v1.json",
        "corpus_manifest_sha256": sha256(out / "manifest_v1.json"),
        "source_split_manifest_path": "model_tuning/generated/splits/split_manifest_v1.json",
        "source_split_manifest_sha256": sha256(source_split_manifest),
        "training_split_manifest_path": "model_tuning/generated/splits/training_split_manifest_v1.json",
        "training_split_manifest_sha256": sha256(training_split_manifest),
        "training_dataset_manifest_path": "model_tuning/generated/training_dataset_manifest_v2.json",
        "training_dataset_manifest_sha256": sha256(training_manifest),
        "training_dataset_manifest_internal_sha256": training.get("manifest_sha256"),
        "split_algorithm": source_split.get("algorithm"),
        "split_seed": source_split.get("seed"),
        "grounded_qa_selection_algorithm": MIXTURE_VERSION,
        "grounded_qa_selection_seed": MIXTURE_SEED,
        "grounded_qa_candidate_rows": len(qa_candidates),
        "grounded_qa_selected_rows": len(qa_selected),
        "input_sha256": corpus.get("input_sha256"),
        "eval_sha256": corpus.get("eval_sha256"),
        "training_rows": (training.get("mixture") or {}).get("training_rows"),
        "grounded_qa_fraction": (training.get("mixture") or {}).get("grounded_qa_fraction"),
    }
    (out / "training_artifact_lock_v3.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return lock


def self_test() -> None:
    required = {
        "build-model-corpus.py",
        "split-model-training-grounded.py",
        "enforce-supplied-claim-grounding.py",
        "build-training-dataset-manifest.py",
    }
    present = {p.name for p in (ROOT / "scripts").iterdir() if p.is_file()}
    missing = sorted(required - present)
    if missing:
        raise AssertionError(f"missing freezer dependencies: {missing}")

    assert grounded_qa_limit(144, 0.20) == 36
    rows = [
        {"id": f"q{i}", "profile_id": f"p{i % 5}", "source_ids": [f"s{i}"]}
        for i in range(20)
    ]
    selected = select_grounded_qa(rows, 8, seed=420)
    again = select_grounded_qa(rows, 8, seed=420)
    assert [row["id"] for row in selected] == [row["id"] for row in again]
    assert len(selected) == 8
    assert len({row["profile_id"] for row in selected}) == 5
    assert select_grounded_qa(rows, 30, seed=420) == sorted(rows, key=lambda row: row["id"])
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
