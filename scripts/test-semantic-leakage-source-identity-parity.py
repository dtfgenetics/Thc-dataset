#!/usr/bin/env python3
"""Guard semantic-leakage source identity behavior against the shared contract.

This is a temporary migration safety test. It compares the semantic leakage
auditor's current source-identity behavior with scripts/source_identity.py so the
auditor can be switched to the shared implementation without silently changing
held-out leakage semantics. Stored citation metadata is never rewritten.
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


def main() -> None:
    semantic = load(SCRIPTS / "audit-model-semantic-leakage.py", "semantic_leakage")
    shared = load(SCRIPTS / "source_identity.py", "shared_source_identity")

    cases = [
        "",
        "doi:10.1000/XYZ.123",
        "10.1000/XYZ.123",
        "https://doi.org/10.1000/xyz.123",
        "http://dx.doi.org/10.1000/XYZ.123",
        "url:https://Example.org/reference/",
        "http://example.org:80/reference#methods",
        "https://example.org:443/reference?utm_source=newsletter&utm_medium=email",
        "https://example.org/reference?fbclid=abc123",
        "https://example.org/reference?gclid=abc123",
        "https://example.org/reference?dclid=abc123",
        "https://example.org/reference?msclkid=abc123",
        "https://example.org/reference?id=alpha&utm_source=x",
        "https://example.org:8443/reference",
        "local-source-id",
    ]

    for value in cases:
        actual = semantic.canonical_source_identity(value)
        expected = shared.canonical_source_identity(value)
        assert actual == expected, (value, actual, expected)

    source_sets = [
        [],
        ["doi:10.1000/XYZ.123", "https://doi.org/10.1000/xyz.123"],
        ["http://example.org/reference", "https://example.org:443/reference#x"],
        ["https://example.org/reference?id=alpha", "https://example.org/reference?id=beta"],
    ]
    for values in source_sets:
        row = {"source_ids": values}
        assert semantic.canonical_sources(row) == shared.canonical_sources(values), values

    print("semantic leakage/shared source identity parity: PASS")


if __name__ == "__main__":
    main()
