#!/usr/bin/env python3
"""Fail closed when corpus provenance aliases undermine dedupe or held-out isolation.

Stored citation/source metadata is never rewritten. Comparison uses the repository-wide
source_identity contract so audits cannot drift from other model-tuning gates.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
import tempfile
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from source_identity import canonical_source_identity, canonical_sources

CORPUS_BUILDER = ROOT / "scripts/build-model-corpus.py"
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"


def load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_rows(rag_rows: list[dict], sft_rows: list[dict], heldout_sources) -> dict:
    heldout = canonical_sources(heldout_sources)
    alias_groups: dict[str, set[str]] = defaultdict(set)
    exact_claim_alias_collisions = []

    for row in rag_rows:
        raw_ids = [str(value) for value in row.get("source_ids") or [] if str(value).strip()]
        canonical_ids = canonical_sources(raw_ids)
        for raw in raw_ids:
            canonical = canonical_source_identity(raw)
            if canonical:
                alias_groups[canonical].add(raw)
        if len(canonical_ids) < len(set(raw_ids)):
            exact_claim_alias_collisions.append({
                "rag_id": row.get("id"),
                "claim_sha256": row.get("claim_sha256"),
                "source_ids": sorted(set(raw_ids)),
                "canonical_source_ids": sorted(canonical_ids),
            })

    sft_heldout_collisions = []
    for row in sft_rows:
        overlap = sorted(canonical_sources(row.get("source_ids") or []) & heldout)
        if overlap:
            sft_heldout_collisions.append({"sft_id": row.get("id"), "canonical_source_ids": overlap})

    if exact_claim_alias_collisions:
        raise ValueError(
            "canonical source aliases survived exact-claim RAG deduplication: "
            + repr(exact_claim_alias_collisions[:5])
        )
    if sft_heldout_collisions:
        raise ValueError("canonical held-out source aliases entered SFT: " + repr(sft_heldout_collisions[:5]))

    return {
        "rag_rows": len(rag_rows),
        "sft_rows": len(sft_rows),
        "heldout_canonical_sources": len(heldout),
        "exact_claim_alias_collisions": 0,
        "sft_heldout_alias_collisions": 0,
        "global_source_alias_groups": {
            canonical: sorted(raws) for canonical, raws in alias_groups.items() if len(raws) > 1
        },
    }


def run(input_path: pathlib.Path, eval_path: pathlib.Path) -> dict:
    corpus = load_module(CORPUS_BUILDER, "grow_doc_corpus_for_canonical_identity_audit")
    rag, sft, _, _ = corpus.build(input_path, eval_path)
    return audit_rows(rag, sft, corpus.eval_source_ids(eval_path))


def expect_audit_failure(rag_rows, sft_rows, heldout_sources, expected: str) -> None:
    try:
        audit_rows(rag_rows, sft_rows, heldout_sources)
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError(f"expected audit failure containing {expected!r}")


def self_test() -> None:
    # Shared contract: safe aliases collapse; meaningful distinctions remain distinct.
    alias_pairs = (
        ("doi:10.1234/ABC", "https://doi.org/10.1234/abc"),
        ("http://Example.COM/path", "https://example.com/path/"),
        ("http://example.com:80/path", "https://example.com/path"),
        ("https://example.com:443/path", "https://example.com/path"),
        ("https://example.com/path?utm_source=x", "https://example.com/path"),
        ("https://example.com/path?gclid=x", "https://example.com/path"),
    )
    for left, right in alias_pairs:
        assert canonical_source_identity(left) == canonical_source_identity(right), (left, right)
    distinct_pairs = (
        ("https://example.com/path?id=1", "https://example.com/path?id=2"),
        ("https://example.com:8443/path", "https://example.com/path"),
        ("https://a.example.com/path", "https://b.example.com/path"),
    )
    for left, right in distinct_pairs:
        assert canonical_source_identity(left) != canonical_source_identity(right), (left, right)

    # Exercise the production builder's already-supported DOI held-out isolation path.
    corpus = load_module(CORPUS_BUILDER, "grow_doc_corpus_builder_source_identity_self_test")
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        profiles = root / "profiles.jsonl"
        heldout = root / "heldout.jsonl"
        profiles.write_text(json.dumps({
            "id": "alias-heldout-profile", "name": "Alias held-out profile",
            "category": "diagnostic", "reviewStatus": "reviewed",
            "summary": "Synthetic self-test only.",
            "sources": [{"title": "Synthetic held-out source", "url": "https://doi.org/10.1000/HELD",
                         "supportedClaims": ["Synthetic claim used only to test source isolation."]}],
        }, separators=(",", ":")) + "\n", encoding="utf-8")
        heldout.write_text(json.dumps({
            "id": "heldout-alias-case", "prompt": "Synthetic held-out prompt",
            "must_cite": ["doi:10.1000/held"],
        }, separators=(",", ":")) + "\n", encoding="utf-8")
        rag, sft, quarantine, stats = corpus.build(profiles, heldout)
        assert len(rag) == 1
        assert sft == []
        assert stats["heldout_profiles_excluded_from_sft"] == 1
        assert any(item.get("reason") == "heldout_source_excluded_from_sft" for item in quarantine)

    audit_rows(
        [{"id": "rag-safe", "claim_sha256": "a", "source_ids": ["doi:10.1000/a"]}],
        [{"id": "sft-safe", "source_ids": ["doi:10.1000/a"]}],
        {"doi:10.1000/held"},
    )
    for left, right in alias_pairs:
        expect_audit_failure(
            [{"id": "rag-alias", "claim_sha256": "b", "source_ids": [left, right]}],
            [], set(), "RAG deduplication",
        )
        expect_audit_failure(
            [], [{"id": "sft-heldout-alias", "source_ids": [left]}], {right}, "held-out",
        )
    for left, right in distinct_pairs:
        audit_rows(
            [{"id": "rag-distinct", "claim_sha256": "c", "source_ids": [left, right]}],
            [], set(),
        )

    print("canonical corpus source-identity audit self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        result = run(args.input, args.eval)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
