#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "model_tuning/eval/heldout_v3.jsonl"
V3_MANIFEST = ROOT / "model_tuning/eval/heldout_v3.manifest.json"

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
    "scripts/audit-split-source-identities.py",
    "scripts/prepare-base-rag-blind-review.py",
    "scripts/validate-adapter-combination-policy.py",
    "model_tuning/config/adapter_combination_policy_v1.json",
    "scripts/audit-model-eval-candidate-leakage.py",
]


def validate_v3_manifest(errors):
    if not V3.exists():
        if V3_MANIFEST.exists():
            errors.append("heldout_v3.manifest.json exists without heldout_v3.jsonl")
        return
    if not V3_MANIFEST.exists():
        errors.append("heldout_v3.jsonl exists without heldout_v3.manifest.json")
        return
    try:
        manifest = json.loads(V3_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid heldout-v3 manifest: {exc}")
        return
    expected_sha = hashlib.sha256(V3.read_bytes()).hexdigest()
    if manifest.get("schema_version") != "grow-doc-heldout-v3-freeze-manifest-v1":
        errors.append("heldout-v3 manifest has unexpected schema_version")
    if manifest.get("sha256") != expected_sha:
        errors.append("heldout-v3 manifest SHA-256 does not match frozen benchmark bytes")
    if manifest.get("cases") != 16:
        errors.append("heldout-v3 manifest must record exactly 16 cases")
    if manifest.get("policy") != "frozen_evaluation_only_never_training":
        errors.append("heldout-v3 manifest missing frozen evaluation-only policy")
    inputs = manifest.get("inputs_sha256")
    if not isinstance(inputs, dict) or "scripts/freeze-heldout-v3.py" not in inputs:
        errors.append("heldout-v3 manifest must bind the freezer in inputs_sha256")


def main():
    expected = "heldout_v3.jsonl" if V3.exists() else "heldout_v2.jsonl"
    forbidden = "heldout_v2.jsonl" if V3.exists() else "heldout_v3.jsonl"
    forbidden_rag_manifest = "heldout_v2.manifest.json" if V3.exists() else "heldout_v3.manifest.json"
    errors = []
    validate_v3_manifest(errors)
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
        if forbidden_rag_manifest in text:
            errors.append(f"{rel}: partial migration reference to {forbidden_rag_manifest}")
    if errors:
        raise SystemExit("migration-state check failed:\n- " + "\n- ".join(errors))
    print(f"migration state: PASS direct_consumers={len(DIRECT_CONSUMERS)}")


if __name__ == "__main__":
    main()
