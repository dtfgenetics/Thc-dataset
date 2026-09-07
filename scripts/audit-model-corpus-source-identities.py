#!/usr/bin/env python3
"""Fail closed when corpus provenance aliases undermine deduplication or held-out isolation.

The production corpus builder intentionally preserves citation bytes. This audit adds a
canonical identity layer for DOI/URL comparison without rewriting those bytes. It rejects:
1. exact-claim RAG rows whose corroborating source_ids collapse to fewer canonical sources;
2. SFT rows whose source_ids canonically overlap held-out must_cite sources.

Global alias groups are reported for cleanup but do not fail solely for existing in-corpus
formatting differences when they do not affect an exact dedupe group or held-out isolation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys
import tempfile
from collections import defaultdict
from urllib.parse import urlsplit, urlunsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS_BUILDER = ROOT / "scripts/build-model-corpus.py"
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_source_identity(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    lowered = raw.lower()
    if lowered.startswith("url:"):
        return canonical_source_identity(raw[4:].strip())
    if lowered.startswith("doi:"):
        payload = raw[4:].strip()
        if not payload:
            return ""
        if payload.lower().startswith(("http://", "https://")):
            canonical = canonical_source_identity(payload)
            return canonical if canonical.startswith("doi:") else f"doi:{payload.lower()}"
        return f"doi:{payload.lower()}"
    if DOI_RE.fullmatch(raw):
        return f"doi:{raw.lower()}"

    parsed = urlsplit(raw)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""
        if host in {"doi.org", "www.doi.org", "dx.doi.org"}:
            payload = path.lstrip("/")
            return f"doi:{payload.lower()}" if payload else ""
        netloc = host
        if parsed.port:
            netloc = f"{host}:{parsed.port}"
        normalized_path = path.rstrip("/") or "/"
        return urlunsplit((parsed.scheme.lower(), netloc, normalized_path, parsed.query, ""))
    return raw


def canonical_sources(values) -> set[str]:
    return {
        identity
        for value in values
        for identity in [canonical_source_identity(str(value))]
        if identity
    }


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
            exact_claim_alias_collisions.append(
                {
                    "rag_id": row.get("id"),
                    "claim_sha256": row.get("claim_sha256"),
                    "source_ids": sorted(set(raw_ids)),
                    "canonical_source_ids": sorted(canonical_ids),
                }
            )

    sft_heldout_collisions = []
    for row in sft_rows:
        canonical = canonical_sources(row.get("source_ids") or [])
        overlap = sorted(canonical & heldout)
        if overlap:
            sft_heldout_collisions.append({"sft_id": row.get("id"), "canonical_source_ids": overlap})

    if exact_claim_alias_collisions:
        raise ValueError(
            "canonical source aliases survived exact-claim RAG deduplication: "
            + repr(exact_claim_alias_collisions[:5])
        )
    if sft_heldout_collisions:
        raise ValueError(
            "canonical held-out source aliases entered SFT: " + repr(sft_heldout_collisions[:5])
        )

    report_aliases = {
        canonical: sorted(raws)
        for canonical, raws in alias_groups.items()
        if len(raws) > 1
    }
    return {
        "rag_rows": len(rag_rows),
        "sft_rows": len(sft_rows),
        "heldout_canonical_sources": len(heldout),
        "exact_claim_alias_collisions": 0,
        "sft_heldout_alias_collisions": 0,
        "global_source_alias_groups": report_aliases,
    }


def run(input_path: pathlib.Path, eval_path: pathlib.Path) -> dict:
    corpus = load_module(CORPUS_BUILDER, "grow_doc_corpus_for_canonical_identity_audit")
    rag, sft, _, _ = corpus.build(input_path, eval_path)
    heldout_sources = corpus.eval_source_ids(eval_path)
    return audit_rows(rag, sft, heldout_sources)


def self_test() -> None:
    assert canonical_source_identity("doi:10.1234/ABC") == "doi:10.1234/abc"
    assert canonical_source_identity("url:https://doi.org/10.1234/AbC") == "doi:10.1234/abc"
    assert canonical_source_identity("https://doi.org/10.1234/AbC") == "doi:10.1234/abc"
    assert canonical_source_identity("HTTPS://Example.COM/path/") == "https://example.com/path"

    corpus = load_module(CORPUS_BUILDER, "grow_doc_corpus_builder_source_identity_self_test")
    for sample in (
        "doi:10.1234/ABC",
        "url:https://doi.org/10.1234/AbC",
        "https://doi.org/10.1234/AbC",
        "HTTPS://Example.COM/path/",
    ):
        assert corpus.canonical_source_identity(sample) == canonical_source_identity(sample)

    # Exercise the production builder, not only this audit helper: a DOI URL in reviewed
    # training data must be excluded when held-out declares the same DOI in canonical form.
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        profiles = root / "profiles.jsonl"
        heldout = root / "heldout.jsonl"
        profiles.write_text(
            json.dumps(
                {
                    "id": "alias-heldout-profile",
                    "name": "Alias held-out profile",
                    "category": "diagnostic",
                    "reviewStatus": "reviewed",
                    "summary": "Synthetic self-test only.",
                    "sources": [
                        {
                            "title": "Synthetic held-out source",
                            "url": "https://doi.org/10.1000/HELD",
                            "supportedClaims": ["Synthetic claim used only to test source isolation."],
                        }
                    ],
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        heldout.write_text(
            json.dumps(
                {
                    "id": "heldout-alias-case",
                    "prompt": "Synthetic held-out prompt",
                    "must_cite": ["doi:10.1000/held"],
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
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

    try:
        audit_rows(
            [{
                "id": "rag-alias",
                "claim_sha256": "b",
                "source_ids": ["doi:10.1000/ABC", "url:https://doi.org/10.1000/abc"],
            }],
            [],
            set(),
        )
    except ValueError as exc:
        assert "RAG deduplication" in str(exc)
    else:
        raise AssertionError("canonical aliases within one deduped claim must fail")

    try:
        audit_rows(
            [],
            [{"id": "sft-heldout-alias", "source_ids": ["url:https://doi.org/10.1000/HELD"]}],
            {"doi:10.1000/held"},
        )
    except ValueError as exc:
        assert "held-out" in str(exc)
    else:
        raise AssertionError("held-out DOI aliases must not enter SFT")

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
