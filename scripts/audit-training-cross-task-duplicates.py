#!/usr/bin/env python3
"""Fail closed when identical assistant supervision survives across task labels.

The training-eligible builder already removes exact duplicates within a task. This audit checks
the remaining strong-evidence SFT + grounded-QA lane globally after citation/source identifiers
are stripped. Identical answer payloads under different task labels can otherwise overweight the
same proposition merely because it was templated into more than one supervision format.

This audit never mutates canonical RAG, grounded-QA, or source metadata. It only reports and fails
on cross-task exact duplicates so remediation stays explicit and reviewable.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys
from collections import defaultdict
from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[1]
ELIGIBLE_BUILDER = ROOT / "scripts/build-training-eligible-supervision.py"
TOKEN_RE = re.compile(r"[a-z0-9]+")
SOURCE_ID_RE = re.compile(r"(?:doi|url|source):\S+", re.IGNORECASE)


def load_module(path: pathlib.Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assistant_text(record: dict) -> str:
    return "\n".join(
        str(message.get("content") or "")
        for message in (record.get("messages") or [])
        if message.get("role") == "assistant"
    ).strip()


def normalized_text(text: str) -> str:
    text = SOURCE_ID_RE.sub(" ", (text or "").lower())
    return " ".join(TOKEN_RE.findall(text))


def audit(records: list[dict]) -> dict:
    by_payload: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        normalized = normalized_text(assistant_text(record))
        if not normalized:
            continue
        by_payload[normalized].append(
            {
                "id": str(record.get("id") or "<missing-id>"),
                "task": str(record.get("task") or "<missing-task>"),
                "profile_id": str(record.get("profile_id") or "<missing-profile>"),
                "source_ids": sorted(str(x) for x in (record.get("source_ids") or [])),
            }
        )

    groups = []
    for rows in by_payload.values():
        tasks = sorted({row["task"] for row in rows})
        ids = sorted({row["id"] for row in rows})
        if len(tasks) <= 1 or len(ids) <= 1:
            continue
        groups.append(
            {
                "tasks": tasks,
                "record_ids": ids,
                "profile_ids": sorted({row["profile_id"] for row in rows}),
                "records": sorted(rows, key=lambda row: (row["task"], row["id"])),
            }
        )

    groups.sort(key=lambda row: (row["tasks"], row["record_ids"]))
    return {
        "schema_version": "grow-doc-training-cross-task-duplicates-v1",
        "policy": {
            "scope": "strong-evidence training-eligible SFT and grounded-QA candidates",
            "rag_first": True,
            "automatic_deletion": False,
            "normalization": "lowercase alphanumeric assistant text with source/citation identifiers removed",
            "cross_task_exact_duplicate_behavior": "hard error; remediate explicitly in weight-training lane only",
            "canonical_rag_mutated": False,
        },
        "candidate_examples": len(records),
        "cross_task_exact_duplicate_group_count": len(groups),
        "cross_task_exact_duplicate_groups": groups[:100],
        "hard_errors": len(groups),
    }


def run() -> dict:
    eligible = load_module(ELIGIBLE_BUILDER, "grow_doc_cross_task_duplicate_eligible")
    sft, qa, eligibility_report = eligible.run(eligible.DEFAULT_INPUT, eligible.DEFAULT_EVAL)
    report = audit(sft + qa)
    report["eligibility_snapshot"] = {
        "training_eligible_sft_examples": len(sft),
        "training_eligible_grounded_qa_examples": len(qa),
        "exact_supervision_duplicates_excluded_within_task": eligibility_report[
            "exact_supervision_duplicates_excluded"
        ],
    }
    return report


def self_test() -> None:
    shared = "Magnesium deficiency can cause interveinal chlorosis on older leaves. Citation: {}"
    records = [
        {
            "id": "sft-a",
            "task": "science_education",
            "profile_id": "mg",
            "source_ids": ["doi:10.x/a"],
            "messages": [{"role": "assistant", "content": shared.format("doi:10.x/a")}],
        },
        {
            "id": "qa-a",
            "task": "grounded_qa",
            "profile_id": "mg",
            "source_ids": ["url:https://example.edu/mg"],
            "messages": [{"role": "assistant", "content": shared.format("url:https://example.edu/mg")}],
        },
        {
            "id": "qa-b",
            "task": "grounded_qa",
            "profile_id": "iron",
            "source_ids": ["doi:10.x/b"],
            "messages": [{"role": "assistant", "content": "Iron deficiency generally presents differently."}],
        },
    ]
    report = audit(records)
    assert report["cross_task_exact_duplicate_group_count"] == 1
    assert report["hard_errors"] == 1
    assert report["cross_task_exact_duplicate_groups"][0]["tasks"] == ["grounded_qa", "science_education"]
    assert set(report["cross_task_exact_duplicate_groups"][0]["record_ids"]) == {"qa-a", "sft-a"}
    print("training cross-task duplicate self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit exact supervision duplication across Grow Doc task labels.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        report = run()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["hard_errors"]:
        print(
            f"training cross-task duplicate audit: FAIL ({report['hard_errors']} duplicate groups)",
            file=sys.stderr,
        )
        return 1
    print("training cross-task duplicate audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
