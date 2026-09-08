#!/usr/bin/env python3
"""Audit evidence tiers on generated Grow Doc supervision examples.

This audit bridges profile-level evidence quality to the actual SFT / grounded-QA records that
would be considered for training. It is intentionally reporting-only for weak-only examples:
those examples remain visible for remediation instead of being silently deleted or repinned.
Broken provenance identities are hard errors because source/citation metadata must stay traceable.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from collections import Counter, defaultdict
from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
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


def build_source_tiers(profiles: list[dict], corpus, evidence) -> dict[str, str]:
    tiers: dict[str, str] = {}
    for profile in profiles:
        for source in profile.get("sources") or []:
            emitted = corpus.source_id(source)
            canonical = corpus.canonical_source_identity(emitted)
            if not canonical:
                continue
            tier = evidence.evidence_tier(source)
            previous = tiers.get(canonical)
            if previous is not None and previous != tier:
                raise ValueError(
                    f"conflicting evidence tiers for {canonical}: {previous} vs {tier}"
                )
            tiers[canonical] = tier
    return tiers


def evaluate(records: list[dict], source_tiers: dict[str, str], corpus) -> dict:
    by_task: dict[str, Counter] = defaultdict(Counter)
    tier_usage = Counter()
    weak_only: list[dict] = []
    unknown: list[dict] = []
    strong_examples = 0

    for record in records:
        task = str(record.get("task") or "<missing-task>")
        record_id = str(record.get("id") or "<missing-id>")
        raw_ids = [str(x) for x in (record.get("source_ids") or []) if str(x).strip()]
        canonical_ids = [corpus.canonical_source_identity(x) for x in raw_ids]
        canonical_ids = [x for x in canonical_ids if x]
        tiers = [source_tiers.get(source_id) for source_id in canonical_ids]
        missing = [source_id for source_id, tier in zip(canonical_ids, tiers) if tier is None]

        by_task[task]["examples"] += 1
        if not canonical_ids or missing:
            by_task[task]["unknown_provenance"] += 1
            unknown.append(
                {
                    "id": record_id,
                    "task": task,
                    "source_ids": raw_ids,
                    "unknown_canonical_source_ids": missing or canonical_ids,
                }
            )
            continue

        for tier in set(tiers):
            tier_usage[str(tier)] += 1

        if any(tier in STRONG_TIERS for tier in tiers):
            strong_examples += 1
            by_task[task]["strong_supported"] += 1
        else:
            by_task[task]["weak_only"] += 1
            weak_only.append(
                {
                    "id": record_id,
                    "task": task,
                    "source_ids": raw_ids,
                    "tiers": sorted(set(str(tier) for tier in tiers)),
                }
            )

    return {
        "schema_version": "grow-doc-example-evidence-tier-audit-v1",
        "policy": {
            "strong_tiers": sorted(STRONG_TIERS),
            "weak_only_behavior": "report for remediation; do not mutate frozen or generated training bytes",
            "unknown_provenance_behavior": "hard error because supervision citations must resolve to source metadata",
            "rag_first": True,
        },
        "examples": len(records),
        "examples_with_strong_evidence": strong_examples,
        "weak_only_examples": len(weak_only),
        "unknown_provenance_examples": len(unknown),
        "tier_usage_by_example": dict(sorted(tier_usage.items())),
        "by_task": {task: dict(sorted(counts.items())) for task, counts in sorted(by_task.items())},
        "weak_only_remediation_queue": weak_only,
        "unknown_provenance": unknown,
        "hard_errors": len(unknown),
    }


def run(input_path: pathlib.Path, eval_path: pathlib.Path) -> dict:
    corpus = load_module(CORPUS_BUILDER, "grow_doc_example_evidence_corpus")
    gqa = load_module(GQA_BUILDER, "grow_doc_example_evidence_gqa")
    evidence = load_module(EVIDENCE_AUDIT, "grow_doc_example_evidence_source_audit")
    profiles = corpus.load_jsonl(input_path)
    source_tiers = build_source_tiers(profiles, corpus, evidence)
    _, sft, _, _ = corpus.build(input_path, eval_path)
    qa, _ = gqa.build(input_path, eval_path)
    report = evaluate(sft + qa, source_tiers, corpus)
    report["sft_examples"] = len(sft)
    report["grounded_qa_examples"] = len(qa)
    report["indexed_source_identities"] = len(source_tiers)
    return report


def self_test() -> None:
    class Corpus:
        @staticmethod
        def canonical_source_identity(value: str) -> str:
            return value.lower()

    source_tiers = {
        "doi:10.x/strong": "scholarly_doi",
        "url:https://example.edu/evidence": "institutional_web",
        "url:https://example.com/blog": "general_web",
    }
    records = [
        {"id": "s1", "task": "science_education", "source_ids": ["DOI:10.X/STRONG"]},
        {"id": "q1", "task": "grounded_qa", "source_ids": ["url:https://example.com/blog"]},
        {"id": "d1", "task": "grounded_diagnostic_reasoning", "source_ids": ["doi:10.x/missing"]},
    ]
    report = evaluate(records, source_tiers, Corpus)
    assert report["examples"] == 3
    assert report["examples_with_strong_evidence"] == 1
    assert report["weak_only_examples"] == 1
    assert report["unknown_provenance_examples"] == 1
    assert report["hard_errors"] == 1
    assert report["weak_only_remediation_queue"][0]["id"] == "q1"
    print("model example evidence tier audit self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit evidence tiers on generated Grow Doc training examples.")
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        report = run(args.input, args.eval)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["hard_errors"]:
        print(
            f"model example evidence tier audit: FAIL ({report['hard_errors']} unresolved provenance examples)",
            file=sys.stderr,
        )
        return 1
    print("model example evidence tier audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
