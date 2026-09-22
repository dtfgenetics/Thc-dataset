#!/usr/bin/env python3
"""Regression guard for Grow Doc source-identity consumers.

This test prevents corpus/evaluation consumers from silently drifting apart while
we migrate their private canonicalizers to scripts/source_identity.py. It compares
identities only; stored source/citation metadata is never rewritten.
"""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shared = load(SCRIPTS / "source_identity.py", "grow_doc_shared_source_identity")
consumers = {
    "corpus_builder": load(SCRIPTS / "build-model-corpus.py", "grow_doc_corpus_builder_identity"),
    "semantic_leakage": load(SCRIPTS / "audit-model-semantic-leakage.py", "grow_doc_semantic_identity"),
    "eval_candidates": load(SCRIPTS / "validate-model-eval-candidates.py", "grow_doc_eval_candidate_identity"),
    "eval_diversity": load(SCRIPTS / "audit-model-eval-candidate-diversity.py", "grow_doc_eval_diversity_identity"),
}

CASES = [
    "",
    "local-source-id",
    "doi:10.1234/ABC.DEF",
    "10.1234/ABC.DEF",
    "https://doi.org/10.1234/ABC.DEF",
    "https://DX.DOI.ORG/10.1234/ABC.DEF",
    "url:https://Example.org/reference/",
    "http://example.org:80/reference#methods",
    "https://example.org:443/reference?utm_source=x&utm_medium=y",
    "https://example.org/reference?fbclid=abc",
    "https://example.org/reference?gclid=abc",
    "https://example.org/reference?dclid=abc",
    "https://example.org/reference?msclkid=abc",
    "https://example.org/reference?id=alpha&utm_source=x",
    "https://example.org:8443/reference?id=alpha",
]


def main() -> int:
    failures = []
    for value in CASES:
        expected = shared.canonical_source_identity(value)
        for name, module in consumers.items():
            actual = module.canonical_source_identity(value)
            if actual != expected:
                failures.append((name, value, expected, actual))

    if failures:
        for name, value, expected, actual in failures:
            print(f"FAIL {name}: {value!r}: shared={expected!r} consumer={actual!r}")
        raise SystemExit(f"source identity consumer parity: FAIL ({len(failures)} mismatches)")

    print(f"source identity consumer parity: PASS ({len(CASES)} cases x {len(consumers)} consumers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
