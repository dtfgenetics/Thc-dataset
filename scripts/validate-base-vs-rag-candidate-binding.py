#!/usr/bin/env python3
"""Fail closed if the frozen base-vs-RAG launcher drifts from the approved base-model registry."""
from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "model_tuning/config/base_model_candidates_v1.json"
LAUNCHER = ROOT / "scripts/run-base-vs-rag-experiment.py"


class BindingError(ValueError):
    pass


def fail(message: str) -> None:
    raise BindingError(message)


def approved_candidate(registry: dict) -> dict:
    candidates = registry.get("candidates") or []
    eligible = [item for item in candidates if item.get("benchmark_eligible") is True]
    if len(eligible) != 1:
        fail(f"expected exactly one benchmark-eligible candidate, found {len(eligible)}")
    candidate = eligible[0]
    if candidate.get("runtime_contract_frozen") is not True:
        fail("benchmark-eligible candidate must have a frozen runtime contract")
    return candidate


def validate_binding(registry: dict, launcher: dict) -> None:
    candidate = approved_candidate(registry)
    contract = registry.get("benchmark_contract") or {}
    checks = {
        "MODEL_REPO": candidate.get("repo_id"),
        "MODEL_REVISION": candidate.get("revision"),
        "TOKENIZER_REVISION": candidate.get("tokenizer_revision"),
        "CHAT_TEMPLATE_SHA256": candidate.get("chat_template_sha256"),
        "BENCHMARK": contract.get("heldout_path"),
        "RAG_SNAPSHOT": contract.get("rag_snapshot_path"),
    }
    for launcher_name, expected in checks.items():
        actual = launcher.get(launcher_name)
        if actual != expected:
            fail(
                f"launcher {launcher_name} drifted from candidate registry: "
                f"expected {expected!r}, got {actual!r}"
            )


def load_launcher(path: Path = LAUNCHER) -> dict:
    return runpy.run_path(str(path), run_name="grow_doc_base_vs_rag_binding_check")


def validate() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    launcher = load_launcher()
    validate_binding(registry, launcher)


def self_test() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    launcher = load_launcher()
    validate_binding(registry, launcher)

    broken = dict(launcher)
    broken["MODEL_REVISION"] = "0" * 40
    try:
        validate_binding(registry, broken)
    except BindingError as exc:
        if "MODEL_REVISION" not in str(exc):
            raise
    else:
        fail("self-test expected model revision drift to fail closed")

    broken_registry = json.loads(json.dumps(registry))
    broken_registry["candidates"][0]["chat_template_sha256"] = "f" * 64
    try:
        validate_binding(broken_registry, launcher)
    except BindingError as exc:
        if "CHAT_TEMPLATE_SHA256" not in str(exc):
            raise
    else:
        fail("self-test expected chat-template drift to fail closed")

    print("base-vs-RAG candidate binding self-test: PASS")


if __name__ == "__main__":
    try:
        if "--self-test" in sys.argv:
            self_test()
        else:
            validate()
            print("base-vs-RAG candidate binding: ok")
    except (BindingError, json.JSONDecodeError, OSError) as exc:
        print(f"base-vs-RAG candidate binding validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
