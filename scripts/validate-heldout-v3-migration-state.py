#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "model_tuning/eval/heldout_v3.jsonl"

# Only files that directly bind the active benchmark belong here. Validators
# that derive the benchmark transitively from the registry/launcher must not
# be required to duplicate a filename literal: their own binding checks cover
# that relationship and duplicating it creates a false migration dependency.
DIRECT_CONSUMERS = [
    "model_tuning/config/base_model_candidates_v1.json",
    "scripts/validate-base-model-candidates.py",
    "scripts/validate-base-model-research.py",
    "scripts/run-base-vs-rag-experiment.py",
    "scripts/build-rag-eval-snapshot.py",
    "scripts/evaluate-rag-depth.py",
    "scripts/audit-required-source-membership.py",
    "scripts/validate-model-eval.py",
    "scripts/build-grounded-qa.py",
    "scripts/split-model-sft.py",
    "scripts/evaluate-sft-relevance-rerank.py",
]


def main():
    expected = "heldout_v3.jsonl" if V3.exists() else "heldout_v2.jsonl"
    forbidden = "heldout_v2.jsonl" if V3.exists() else "heldout_v3.jsonl"
    errors = []
    for rel in DIRECT_CONSUMERS:
        path = ROOT / rel
        if not path.exists():
            errors.append(f"missing consumer: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if expected not in text:
            errors.append(f"{rel}: missing {expected}")
        if forbidden in text:
            errors.append(f"{rel}: partial migration reference to {forbidden}")
    if errors:
        raise SystemExit("migration-state check failed:\n- " + "\n- ".join(errors))
    print(f"migration state: PASS direct_consumers={len(DIRECT_CONSUMERS)}")


if __name__ == "__main__":
    main()
