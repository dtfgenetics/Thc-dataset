#!/usr/bin/env python3
"""Build a training-eligible Grow Doc supervision lane from strong evidence only.

The canonical RAG corpus remains unchanged and may retain reviewed general-web evidence for
retrieval/support. This script creates a stricter candidate lane for weight updates: every cited
source in an SFT or grounded-QA record must resolve to scholarly DOI or institutional evidence.
Mixed-tier and weak-only examples are reported for remediation rather than silently upgraded.
Held-out isolation remains delegated to the existing corpus/grounded-QA builders.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from collections import Counter
from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
DEFAULT_OUT = ROOT / "model_tuning/generated/training_eligible"
CORPUS_BUILDER = ROOT / "scripts/build-model-corpus.py"
GQA_BUILDER = ROOT / "scripts/build-grounded-qa.py"
EVIDENCE_AUDIT = ROOT / "scripts/audit-model-source-evidence-quality.py"
STRONG_TIERS = {"scholarly_doi", "institutional_web"}


def load_module(path: pathlib.Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_tier_index(profiles: list[dict], corpus, evidence) -> dict[str, str]:
    index: dict[str, str] = {}
    for profile in profiles:
        for source in profile.get("sources") or []:
            raw_id = corpus.source_id(source)
            canonical = corpus.canonical_source_identity(raw_id)
            if not canonical:
                continue
            tier = evidence.evidence_tier(source)
            previous = index.get(canonical)
            if previous is not None and previous != tier:
                raise ValueError(f"conflicting evidence tiers for {canonical}: {previous} vs {tier}")
            index[canonical] = tier
    return index


def classify_record(record: dict, tiers: dict[str, str], corpus) -> tuple[str, dict]:
    record_id = str(record.get("id") or "<missing-id>")
    task = str(record.get("task") or "<missing-task>")
    raw_ids = [str(x) for x in (record.get("source_ids") or []) if str(x).strip()]
    canonical_ids = [corpus.canonical_source_identity(x) for x in raw_ids]
    canonical_ids = [x for x in canonical_ids if x]
    resolved = [(source_id, tiers.get(source_id)) for source_id in canonical_ids]
    missing = [source_id for source_id, tier in resolved if tier is None]
    detail = {
        "id": record_id,
        "task": task,
        "source_ids": raw_ids,
        "tiers": sorted({str(tier) for _, tier in resolved if tier is not None}),
    }
    if not canonical_ids or missing:
        detail["unknown_canonical_source_ids"] = missing or canonical_ids
        return "unknown_provenance", detail
    strong = [tier in STRONG_TIERS for _, tier in resolved]
    if all(strong):
        return "training_eligible", detail
    if any(strong):
        return "mixed_tier", detail
    return "weak_only", detail


def evaluate(records: list[dict], tiers: dict[str, str], corpus) -> tuple[list[dict], dict]:
    eligible: list[dict] = []
    queues = {
        "mixed_tier": [],
        "weak_only": [],
        "unknown_provenance": [],
    }
    by_task: dict[str, Counter] = {}
    counts = Counter()

    for record in records:
        status, detail = classify_record(record, tiers, corpus)
        task = detail["task"]
        if task not in by_task:
            by_task[task] = Counter()
        by_task[task][status] += 1
        counts[status] += 1
        if status == "training_eligible":
            eligible.append(record)
        else:
            queues[status].append(detail)

    report = {
        "schema_version": "grow-doc-training-eligible-supervision-v1",
        "policy": {
            "rag_first": True,
            "rag_corpus_mutated": False,
            "strong_tiers": sorted(STRONG_TIERS),
            "training_requirement": "every cited source in a supervision record must be training-grade",
            "mixed_tier_behavior": "exclude from weight-training candidate lane; keep available for remediation/retrieval",
            "weak_only_behavior": "exclude from weight-training candidate lane; keep available for remediation/retrieval",
            "unknown_provenance_behavior": "hard error",
        },
        "candidate_examples": len(records),
        "training_eligible_examples": len(eligible),
        "mixed_tier_examples": counts["mixed_tier"],
        "weak_only_examples": counts["weak_only"],
        "unknown_provenance_examples": counts["unknown_provenance"],
        "by_task": {task: dict(sorted(counter.items())) for task, counter in sorted(by_task.items())},
        "mixed_tier_remediation_queue": queues["mixed_tier"],
        "weak_only_remediation_queue": queues["weak_only"],
        "unknown_provenance": queues["unknown_provenance"],
        "hard_errors": counts["unknown_provenance"],
    }
    return eligible, report


def write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def run(input_path: pathlib.Path, eval_path: pathlib.Path) -> tuple[list[dict], list[dict], dict]:
    corpus = load_module(CORPUS_BUILDER, "grow_doc_training_eligible_corpus")
    gqa = load_module(GQA_BUILDER, "grow_doc_training_eligible_gqa")
    evidence = load_module(EVIDENCE_AUDIT, "grow_doc_training_eligible_evidence")
    profiles = corpus.load_jsonl(input_path)
    tiers = source_tier_index(profiles, corpus, evidence)
    _, sft, _, _ = corpus.build(input_path, eval_path)
    qa, _ = gqa.build(input_path, eval_path)
    eligible, report = evaluate(sft + qa, tiers, corpus)
    eligible_ids = {row["id"] for row in eligible}
    eligible_sft = [row for row in sft if row["id"] in eligible_ids]
    eligible_qa = [row for row in qa if row["id"] in eligible_ids]
    report["sft_candidate_examples"] = len(sft)
    report["grounded_qa_candidate_examples"] = len(qa)
    report["training_eligible_sft_examples"] = len(eligible_sft)
    report["training_eligible_grounded_qa_examples"] = len(eligible_qa)
    report["indexed_source_identities"] = len(tiers)
    return eligible_sft, eligible_qa, report


def self_test() -> None:
    class Corpus:
        @staticmethod
        def canonical_source_identity(value: str) -> str:
            return value.lower()

    tiers = {
        "doi:10.x/strong": "scholarly_doi",
        "url:https://example.edu/guide": "institutional_web",
        "url:https://example.com/report": "general_web",
    }
    records = [
        {"id": "a", "task": "science_education", "source_ids": ["DOI:10.X/STRONG"]},
        {"id": "b", "task": "grounded_qa", "source_ids": ["url:https://example.com/report"]},
        {"id": "c", "task": "grounded_diagnostic_reasoning", "source_ids": ["doi:10.x/strong", "url:https://example.com/report"]},
        {"id": "d", "task": "grounded_qa", "source_ids": ["doi:10.x/missing"]},
        {"id": "e", "task": "differential_and_next_test", "source_ids": ["url:https://example.edu/guide"]},
    ]
    eligible, report = evaluate(records, tiers, Corpus)
    assert [row["id"] for row in eligible] == ["a", "e"]
    assert report["training_eligible_examples"] == 2
    assert report["weak_only_examples"] == 1
    assert report["mixed_tier_examples"] == 1
    assert report["unknown_provenance_examples"] == 1
    assert report["hard_errors"] == 1
    print("training-eligible supervision self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build strong-evidence Grow Doc supervision candidates.")
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        eligible_sft, eligible_qa, report = run(args.input, args.eval)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["hard_errors"]:
        print(
            f"training-eligible supervision: FAIL ({report['hard_errors']} unresolved provenance examples)",
            file=sys.stderr,
        )
        return 1

    if not args.check_only:
        write_jsonl(args.out / "sft_v1.jsonl", eligible_sft)
        write_jsonl(args.out / "grounded_qa_v1.jsonl", eligible_qa)
    print("training-eligible supervision: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
