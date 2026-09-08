#!/usr/bin/env python3
"""Validate Grow Doc research-only base-model candidate registry.

The gate is intentionally conservative: a candidate may be recorded for research
without being runnable, but any candidate marked benchmark_eligible or
training_eligible must carry the immutable contracts needed for reproducible
Grow Doc evaluation/training.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

SHA40 = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_SLICES = {
    "factuality",
    "diagnostic",
    "hallucination",
    "citation_accuracy",
    "science",
    "education",
    "grounded_qa",
    "regression",
}
PROMOTION_FIELDS = {
    "revision",
    "tokenizer_hash",
    "chat_template_hash",
    "decoding_contract",
    "dependency_lock",
    "hardware_contract",
    "heldout_contract",
    "rag_contract",
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def valid_https(url: object) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot parse {path}: {exc}"]

    if data.get("schema_version") != 1:
        fail(errors, "schema_version must equal 1")

    policy = data.get("selection_policy")
    if not isinstance(policy, dict):
        fail(errors, "selection_policy must be an object")
        policy = {}

    if policy.get("rag_first") is not True:
        fail(errors, "selection_policy.rag_first must be true")

    slices = policy.get("required_slices")
    if not isinstance(slices, list):
        fail(errors, "selection_policy.required_slices must be a list")
    else:
        missing = REQUIRED_SLICES - set(slices)
        if missing:
            fail(errors, f"required_slices missing: {sorted(missing)}")

    heldout_path = policy.get("heldout_path")
    if heldout_path != "model_tuning/eval/heldout_v2.jsonl":
        fail(errors, "heldout_path must remain model_tuning/eval/heldout_v2.jsonl")

    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return errors + ["candidates must be a non-empty list"]

    ids: set[str] = set()
    repo_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        prefix = f"candidate[{index}]"
        if not isinstance(candidate, dict):
            fail(errors, f"{prefix} must be an object")
            continue

        cid = candidate.get("id")
        if not isinstance(cid, str) or not cid.strip():
            fail(errors, f"{prefix}.id must be non-empty")
        elif cid in ids:
            fail(errors, f"duplicate candidate id: {cid}")
        else:
            ids.add(cid)

        repo_id = candidate.get("repo_id")
        if not isinstance(repo_id, str) or "/" not in repo_id:
            fail(errors, f"{prefix}.repo_id must be owner/name")
        elif repo_id in repo_ids:
            fail(errors, f"duplicate repo_id: {repo_id}")
        else:
            repo_ids.add(repo_id)

        observed = candidate.get("observed_revision")
        if not isinstance(observed, str) or not SHA40.fullmatch(observed):
            fail(errors, f"{prefix}.observed_revision must be a 40-char lowercase git SHA")

        if not valid_https(candidate.get("upstream_evidence")):
            fail(errors, f"{prefix}.upstream_evidence must be an https URL")

        benchmark_eligible = candidate.get("benchmark_eligible")
        training_eligible = candidate.get("training_eligible")
        if not isinstance(benchmark_eligible, bool):
            fail(errors, f"{prefix}.benchmark_eligible must be boolean")
        if not isinstance(training_eligible, bool):
            fail(errors, f"{prefix}.training_eligible must be boolean")

        blockers = candidate.get("blockers")
        if not isinstance(blockers, list):
            fail(errors, f"{prefix}.blockers must be a list")
            blockers = []

        if training_eligible and not benchmark_eligible:
            fail(errors, f"{prefix}: training_eligible requires benchmark_eligible")

        if benchmark_eligible or training_eligible:
            if blockers:
                fail(errors, f"{prefix}: eligible candidates must have no blockers")
            contract = candidate.get("verified_contract")
            if not isinstance(contract, dict):
                fail(errors, f"{prefix}: eligible candidate requires verified_contract")
            else:
                missing_fields = sorted(PROMOTION_FIELDS - set(contract))
                if missing_fields:
                    fail(errors, f"{prefix}.verified_contract missing {missing_fields}")
                revision = contract.get("revision")
                if revision != observed:
                    fail(errors, f"{prefix}.verified_contract.revision must equal observed_revision")
                for field in PROMOTION_FIELDS - {"revision"}:
                    value = contract.get(field)
                    if not isinstance(value, str) or not value.strip():
                        fail(errors, f"{prefix}.verified_contract.{field} must be non-empty")
        else:
            if not blockers:
                fail(errors, f"{prefix}: research-only candidate must document blockers")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        default="model_tuning/config/base_model_research_2026-09-08.json",
    )
    args = parser.parse_args()
    errors = validate(Path(args.path))
    if errors:
        print("Base-model research registry validation FAILED:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Base-model research registry validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
