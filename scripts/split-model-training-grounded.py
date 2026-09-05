#!/usr/bin/env python3
"""Materialize leak-safe train/dev splits after strict supplied-claim grounding.

This wraps the existing source-component splitter. Upstream SFT/GQA builders remain
candidate generators; every record is rewritten and validated at this boundary before
it can enter a train or dev artifact.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS_BUILDER = ROOT / "scripts/build-model-corpus.py"
GQA_BUILDER = ROOT / "scripts/build-grounded-qa.py"
SPLITTER = ROOT / "scripts/split-model-sft.py"
GROUNDING = ROOT / "scripts/enforce-supplied-claim-grounding.py"
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
DEFAULT_OUT = ROOT / "model_tuning/generated/splits"


def load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_grounded_split(input_path: pathlib.Path, eval_path: pathlib.Path, out: pathlib.Path, *, seed: int, dev_fraction: float, check_only: bool) -> dict:
    corpus = load_module(CORPUS_BUILDER, "grow_doc_candidate_corpus")
    gqa_builder = load_module(GQA_BUILDER, "grow_doc_candidate_gqa")
    splitter = load_module(SPLITTER, "grow_doc_source_splitter")
    grounding = load_module(GROUNDING, "grow_doc_grounding")

    _, sft, _, corpus_stats = corpus.build(input_path, eval_path)
    grounded_qa, gqa_stats = gqa_builder.build(input_path, eval_path)

    candidate_rows = [dict(row, _split_lane="sft") for row in sft]
    candidate_rows.extend(dict(row, _split_lane="grounded_qa") for row in grounded_qa)
    sanitized = grounding.sanitize_records(candidate_rows)

    heldout_sources = corpus.eval_source_ids(eval_path)
    train, dev, manifest = splitter.split_records(
        sanitized,
        heldout_sources,
        corpus.norm,
        seed=seed,
        dev_fraction=dev_fraction,
    )
    splitter.add_hashes(manifest, train, dev)
    manifest.update(
        {
            "schema_version": "grow-doc-model-split-v2",
            "grounding_policy": "supplied_claims_only_v1",
            "grounding_enforced_before_split": True,
            "candidate_records": len(candidate_rows),
            "sanitized_records": len(sanitized),
            "input_sha256": corpus_stats["input_sha256"],
            "eval_sha256": corpus_stats["eval_sha256"],
            "source_sft_records": corpus_stats["sft_examples"],
            "source_grounded_qa_records": gqa_stats["grounded_qa_examples"],
            "source_corpus_policy": corpus_stats["policy"],
            "grounded_qa_policy": gqa_stats["policy"],
        }
    )
    if len(candidate_rows) != len(sanitized):
        raise ValueError("grounding transformation unexpectedly changed record count")
    for row in train + dev:
        errors = grounding.validate_row(row)
        if errors:
            raise ValueError("post-split grounding validation failed: " + "; ".join(errors[:3]))
    if not check_only:
        splitter.materialize(out, train, dev, manifest)
    return manifest


def self_test() -> None:
    grounding = load_module(GROUNDING, "grow_doc_grounding_selftest")
    grounding.self_test()
    required = [CORPUS_BUILDER, GQA_BUILDER, SPLITTER, GROUNDING]
    assert all(path.exists() for path in required)
    print("grounded model splitter self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=420)
    parser.add_argument("--dev-fraction", type=float, default=0.20)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        manifest = build_grounded_split(
            args.input,
            args.eval,
            args.out,
            seed=args.seed,
            dev_fraction=args.dev_fraction,
            check_only=args.check_only,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
