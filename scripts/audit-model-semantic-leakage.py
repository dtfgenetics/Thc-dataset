#!/usr/bin/env python3
"""Audit Grow Doc training candidates for held-out semantic leakage.

This is deliberately conservative. Exact normalized prompt leakage and held-out
source reuse are hard failures. High-similarity paraphrases are reported for human
review rather than automatically deleted because scientifically distinct examples
can share substantial vocabulary.

The audit builds the current reviewed SFT and grounded-QA candidates in memory;
it does not train a model or mutate generated datasets.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS_BUILDER = ROOT / "scripts/build-model-corpus.py"
GQA_BUILDER = ROOT / "scripts/build-grounded-qa.py"
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"


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


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def tokens(text: str) -> set[str]:
    return set(norm(text).split())


def user_text(row: dict) -> str:
    parts = []
    for message in row.get("messages") or []:
        if (message.get("role") or "").strip().lower() == "user":
            parts.append(message.get("content") or "")
    return "\n".join(parts).strip()


def full_training_text(row: dict) -> str:
    return "\n".join((m.get("content") or "") for m in row.get("messages") or []).strip()


def eval_text(row: dict) -> str:
    parts = [row.get("prompt") or ""]
    parts.extend(row.get("expected_points") or [])
    return "\n".join(parts).strip()


def similarity(left: str, right: str) -> tuple[float, float, float]:
    lt, rt = tokens(left), tokens(right)
    if not lt or not rt:
        return 0.0, 0.0, 0.0
    overlap = len(lt & rt)
    containment = overlap / min(len(lt), len(rt))
    jaccard = overlap / len(lt | rt)
    length_ratio = min(len(lt), len(rt)) / max(len(lt), len(rt))
    return containment, jaccard, length_ratio


def canonical_sources(row: dict) -> set[str]:
    return {str(value).strip().lower() for value in row.get("source_ids") or [] if str(value).strip()}


def heldout_sources(eval_rows: list[dict]) -> set[str]:
    result = set()
    for row in eval_rows:
        for value in row.get("must_cite") or []:
            value = str(value).strip().lower()
            if value:
                result.add(value)
    return result


def audit(training_rows: list[dict], eval_rows: list[dict], *, near_limit: int = 25) -> dict:
    errors: list[str] = []
    near: list[dict] = []
    eval_sources = heldout_sources(eval_rows)

    eval_prompt_index: dict[str, list[str]] = {}
    for row in eval_rows:
        key = norm(row.get("prompt") or "")
        if key:
            eval_prompt_index.setdefault(key, []).append(row.get("id") or "<missing>")

    for train in training_rows:
        tid = train.get("id") or "<missing>"
        lane = train.get("_audit_lane") or train.get("task") or "unknown"
        source_overlap = sorted(canonical_sources(train) & eval_sources)
        if source_overlap:
            errors.append(f"{tid}: held-out source leakage in {lane}: {source_overlap}")

        prompt = user_text(train)
        prompt_key = norm(prompt)
        if prompt_key and prompt_key in eval_prompt_index:
            errors.append(
                f"{tid}: exact normalized user-prompt leakage into held-out cases {eval_prompt_index[prompt_key]}"
            )

        train_semantic = full_training_text(train)
        if len(tokens(train_semantic)) < 8:
            continue
        for heldout in eval_rows:
            heldout_semantic = eval_text(heldout)
            if len(tokens(heldout_semantic)) < 8:
                continue
            containment, jaccard, length_ratio = similarity(train_semantic, heldout_semantic)
            # Reporting-only threshold: intentionally conservative and never auto-deletes.
            if containment >= 0.78 and jaccard >= 0.50 and length_ratio >= 0.45:
                near.append(
                    {
                        "training_id": tid,
                        "training_lane": lane,
                        "heldout_id": heldout.get("id") or "<missing>",
                        "containment": round(containment, 3),
                        "jaccard": round(jaccard, 3),
                        "length_ratio": round(length_ratio, 3),
                    }
                )

    near.sort(
        key=lambda row: (
            -row["jaccard"],
            -row["containment"],
            row["training_id"],
            row["heldout_id"],
        )
    )
    return {
        "training_records": len(training_rows),
        "heldout_records": len(eval_rows),
        "heldout_sources": len(eval_sources),
        "hard_leakage_errors": len(errors),
        "near_duplicate_pairs": len(near),
        "near_duplicate_examples": near[:near_limit],
        "errors": errors,
        "policy": {
            "exact_prompt_overlap": "fail",
            "heldout_source_overlap": "fail",
            "semantic_near_duplicate": "report_for_human_review",
            "auto_delete_near_duplicates": False,
        },
    }


def build_current(input_path: pathlib.Path, eval_path: pathlib.Path) -> tuple[list[dict], list[dict]]:
    corpus = load_module(CORPUS_BUILDER, "grow_doc_semantic_audit_corpus")
    gqa = load_module(GQA_BUILDER, "grow_doc_semantic_audit_gqa")
    _, sft, _, _ = corpus.build(input_path, eval_path)
    qa, _ = gqa.build(input_path, eval_path)
    combined = [dict(row, _audit_lane="sft") for row in sft]
    combined.extend(dict(row, _audit_lane="grounded_qa") for row in qa)
    return combined, load_jsonl(eval_path)


def self_test() -> None:
    heldout = [
        {
            "id": "eval-1",
            "prompt": "Explain why visual symptoms alone cannot prove calcium deficiency in cannabis plants.",
            "expected_points": ["Use cultivation context and measurements before confirmation."],
            "must_cite": ["doi:10.test/held"],
        }
    ]
    clean = {
        "id": "train-clean",
        "source_ids": ["doi:10.test/train"],
        "messages": [
            {"role": "user", "content": "Describe a cautious diagnostic workflow for an unfamiliar leaf disorder."},
            {"role": "assistant", "content": "Gather context, inspect multiple causes, and confirm with measurements."},
        ],
        "_audit_lane": "sft",
    }
    assert not audit([clean], heldout)["errors"]

    exact = dict(clean)
    exact["id"] = "train-exact"
    exact["messages"] = [
        {"role": "user", "content": heldout[0]["prompt"]},
        {"role": "assistant", "content": "Confirm with context and measurements."},
    ]
    report = audit([exact], heldout)
    assert report["hard_leakage_errors"] == 1
    assert "exact normalized user-prompt leakage" in report["errors"][0]

    source_leak = dict(clean)
    source_leak["id"] = "train-source-leak"
    source_leak["source_ids"] = ["doi:10.test/held"]
    report = audit([source_leak], heldout)
    assert report["hard_leakage_errors"] == 1
    assert "held-out source leakage" in report["errors"][0]

    paraphrase = dict(clean)
    paraphrase["id"] = "train-near"
    paraphrase["messages"] = [
        {
            "role": "user",
            "content": "Explain why cannabis calcium deficiency cannot be proven from visual symptoms alone and needs cultivation context.",
        },
        {
            "role": "assistant",
            "content": "Use measurements and cultivation context before confirming calcium deficiency from the observed symptoms.",
        },
    ]
    report = audit([paraphrase], heldout)
    assert report["hard_leakage_errors"] == 0
    assert report["near_duplicate_pairs"] >= 1
    print("model semantic leakage self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--near-limit", type=int, default=25)
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        training_rows, eval_rows = build_current(args.input, args.eval)
        report = audit(training_rows, eval_rows, near_limit=args.near_limit)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"]:
        print(f"semantic leakage audit: FAIL ({len(report['errors'])} hard errors)", file=sys.stderr)
        return 1
    print("semantic leakage audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
