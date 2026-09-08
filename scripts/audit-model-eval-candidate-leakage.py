#!/usr/bin/env python3
"""Audit Grow Doc evaluation candidates for leakage before benchmark promotion.

Hard failures:
- canonical source overlap with current SFT or grounded-QA candidates;
- exact normalized prompt overlap with current SFT or grounded-QA candidates;
- canonical source overlap with frozen heldout_v2;
- exact normalized prompt overlap with frozen heldout_v2.

High-similarity semantic pairs are reported for independent human review rather
than auto-deleted, because scientifically distinct diagnostic cases can share
substantial vocabulary.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEMANTIC_AUDIT = ROOT / "scripts/audit-model-semantic-leakage.py"
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_HELDOUT = ROOT / "model_tuning/eval/heldout_v2.jsonl"
DEFAULT_MANIFESTS = (
    ROOT / "model_tuning/eval/candidates/pathogen_expansion_v1.manifest.json",
    ROOT / "model_tuning/eval/candidates/heldout_v3_expansion_v1.manifest.json",
)
DEFAULT_DIRECT_DATASETS = (
    ROOT / "model_tuning/eval/heldout_v3_candidates.jsonl",
)


def load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def load_candidate_rows(manifests: list[pathlib.Path], direct_datasets: list[pathlib.Path]) -> list[dict]:
    rows: list[dict] = []
    seen_ids: set[str] = set()

    def add_rows(dataset_path: pathlib.Path) -> None:
        for row in load_jsonl(dataset_path):
            rid = row.get("id")
            if not isinstance(rid, str) or not rid:
                raise ValueError(f"{dataset_path}: candidate missing id")
            if rid in seen_ids:
                raise ValueError(f"duplicate candidate id across candidate datasets: {rid}")
            seen_ids.add(rid)
            rows.append(row)

    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        dataset_rel = manifest.get("dataset")
        if not isinstance(dataset_rel, str) or not dataset_rel:
            raise ValueError(f"{manifest_path}: missing dataset")
        add_rows(ROOT / dataset_rel)

    for dataset_path in direct_datasets:
        add_rows(dataset_path)

    return rows


def eval_rows_as_training(rows: list[dict], lane: str) -> list[dict]:
    converted = []
    for row in rows:
        converted.append(
            {
                "id": row.get("id") or "<missing>",
                "source_ids": list(row.get("must_cite") or []),
                "messages": [
                    {"role": "user", "content": row.get("prompt") or ""},
                    {
                        "role": "assistant",
                        "content": "\n".join(str(value) for value in row.get("expected_points") or []),
                    },
                ],
                "_audit_lane": lane,
            }
        )
    return converted


def audit_all(
    input_path: pathlib.Path,
    heldout_path: pathlib.Path,
    manifests: list[pathlib.Path],
    direct_datasets: list[pathlib.Path],
) -> dict:
    semantic = load_module(SEMANTIC_AUDIT, "grow_doc_candidate_leakage_semantic")
    training_rows, heldout_rows = semantic.build_current(input_path, heldout_path)
    candidate_rows = load_candidate_rows(manifests, direct_datasets)

    corpus_report = semantic.audit(training_rows, candidate_rows)
    heldout_report = semantic.audit(eval_rows_as_training(candidate_rows, "candidate_eval"), heldout_rows)

    errors = [f"training/dev: {value}" for value in corpus_report["errors"]]
    errors.extend(f"heldout_v2: {value}" for value in heldout_report["errors"])
    return {
        "candidate_records": len(candidate_rows),
        "training_and_grounded_qa_records_checked": len(training_rows),
        "heldout_v2_records_checked": len(heldout_rows),
        "hard_leakage_errors": len(errors),
        "errors": errors,
        "training_dev_near_duplicate_pairs": corpus_report["near_duplicate_pairs"],
        "training_dev_near_duplicate_examples": corpus_report["near_duplicate_examples"],
        "heldout_v2_near_duplicate_pairs": heldout_report["near_duplicate_pairs"],
        "heldout_v2_near_duplicate_examples": heldout_report["near_duplicate_examples"],
        "policy": {
            "canonical_source_overlap_with_training_dev": "fail",
            "exact_prompt_overlap_with_training_dev": "fail",
            "canonical_source_overlap_with_heldout_v2": "fail",
            "exact_prompt_overlap_with_heldout_v2": "fail",
            "semantic_near_duplicate": "report_for_independent_human_review",
            "candidate_status_after_pass": "candidate_only_not_promotion_eligible",
        },
    }


def self_test() -> None:
    semantic = load_module(SEMANTIC_AUDIT, "grow_doc_candidate_leakage_selftest")
    candidate = {
        "id": "candidate-clean",
        "prompt": "How should an evaluator separate a visual clue from a confirmed diagnosis?",
        "expected_points": ["Request independent measurements before confirmation."],
        "must_cite": ["doi:10.test/candidate"],
    }
    training = {
        "id": "train-clean",
        "source_ids": ["doi:10.test/train"],
        "messages": [
            {"role": "user", "content": "Explain a cautious workflow for reviewing plant observations."},
            {"role": "assistant", "content": "Separate observations from causes and gather measurements."},
        ],
        "_audit_lane": "sft",
    }
    assert semantic.audit([training], [candidate])["hard_leakage_errors"] == 0

    source_leak = dict(training, id="train-leak", source_ids=["https://doi.org/10.TEST/CANDIDATE"])
    assert semantic.audit([source_leak], [candidate])["hard_leakage_errors"] == 1

    exact = dict(training, id="train-exact")
    exact["messages"] = [
        {"role": "user", "content": candidate["prompt"]},
        {"role": "assistant", "content": "Use measurements."},
    ]
    assert semantic.audit([exact], [candidate])["hard_leakage_errors"] == 1

    heldout = [{
        "id": "heldout-1",
        "prompt": "Explain an unrelated benchmark question.",
        "expected_points": ["Keep benchmark sources isolated."],
        "must_cite": ["doi:10.test/heldout"],
    }]
    candidate_alias = dict(candidate, must_cite=["https://DOI.org/10.TEST/HELDOUT"])
    converted = eval_rows_as_training([candidate_alias], "candidate_eval")
    assert semantic.audit(converted, heldout)["hard_leakage_errors"] == 1
    print("model eval candidate leakage self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--heldout", type=pathlib.Path, default=DEFAULT_HELDOUT)
    parser.add_argument("--manifest", action="append", type=pathlib.Path, dest="manifests")
    parser.add_argument("--candidate-dataset", action="append", type=pathlib.Path, dest="candidate_datasets")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    manifests = args.manifests or list(DEFAULT_MANIFESTS)
    direct_datasets = args.candidate_datasets or list(DEFAULT_DIRECT_DATASETS)
    try:
        report = audit_all(args.input, args.heldout, manifests, direct_datasets)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["hard_leakage_errors"]:
        print(f"candidate leakage audit: FAIL ({report['hard_leakage_errors']} hard errors)", file=sys.stderr)
        return 1
    print("candidate leakage audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
