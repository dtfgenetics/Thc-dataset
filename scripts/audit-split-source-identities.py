#!/usr/bin/env python3
"""Audit Grow Doc train/dev source isolation using canonical provenance identities.

This is intentionally read-only. It rebuilds candidate records in memory, delegates
record assignment to the production splitter, then checks the resulting partitions
with stricter DOI/URL canonicalization so formatting aliases cannot hide leakage.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import sys
from collections import defaultdict
from urllib.parse import urlsplit, urlunsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS_BUILDER = ROOT / "scripts/build-model-corpus.py"
GQA_BUILDER = ROOT / "scripts/build-grounded-qa.py"
SPLITTER = ROOT / "scripts/split-model-sft.py"
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
    if lowered.startswith("doi:"):
        payload = raw[4:].strip()
        return f"doi:{payload.lower()}" if payload else ""
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
    return {identity for value in values for identity in [canonical_source_identity(str(value))] if identity}


def audit_partitions(train: list[dict], dev: list[dict], heldout_sources: set[str]) -> dict:
    train_sources = canonical_sources(sid for row in train for sid in row.get("source_ids") or [])
    dev_sources = canonical_sources(sid for row in dev for sid in row.get("source_ids") or [])
    heldout = canonical_sources(heldout_sources)

    train_dev_overlap = sorted(train_sources & dev_sources)
    heldout_overlap = sorted((train_sources | dev_sources) & heldout)
    if train_dev_overlap:
        raise ValueError(f"canonical source leakage across train/dev: {train_dev_overlap}")
    if heldout_overlap:
        raise ValueError(f"canonical held-out source leakage into train/dev: {heldout_overlap}")

    aliases: dict[str, set[str]] = defaultdict(set)
    for row in train + dev:
        for raw in row.get("source_ids") or []:
            canonical = canonical_source_identity(str(raw))
            if canonical:
                aliases[canonical].add(str(raw))
    alias_groups = {key: sorted(values) for key, values in aliases.items() if len(values) > 1}
    return {
        "train_canonical_sources": len(train_sources),
        "dev_canonical_sources": len(dev_sources),
        "heldout_canonical_sources": len(heldout),
        "train_dev_overlap": 0,
        "heldout_overlap": 0,
        "source_alias_groups": alias_groups,
    }


def run(input_path: pathlib.Path, eval_path: pathlib.Path) -> dict:
    corpus = load_module(CORPUS_BUILDER, "grow_doc_corpus_for_source_identity_audit")
    gqa = load_module(GQA_BUILDER, "grow_doc_gqa_for_source_identity_audit")
    splitter = load_module(SPLITTER, "grow_doc_splitter_for_source_identity_audit")

    _, sft, _, _ = corpus.build(input_path, eval_path)
    grounded_qa, _ = gqa.build(input_path, eval_path)
    combined = [dict(row, _split_lane="sft") for row in sft]
    combined.extend(dict(row, _split_lane="grounded_qa") for row in grounded_qa)
    heldout_sources = corpus.eval_source_ids(eval_path)
    train, dev, _ = splitter.split_records(
        combined,
        heldout_sources,
        corpus.norm,
        seed=splitter.DEFAULT_SEED,
        dev_fraction=splitter.DEFAULT_DEV_FRACTION,
    )
    result = audit_partitions(train, dev, heldout_sources)
    result.update({"candidate_records": len(combined), "train_records": len(train), "dev_records": len(dev)})
    return result


def self_test() -> None:
    assert canonical_source_identity("doi:10.1234/ABC") == "doi:10.1234/abc"
    assert canonical_source_identity("https://doi.org/10.1234/AbC") == "doi:10.1234/abc"
    assert canonical_source_identity("10.1234/ABC") == "doi:10.1234/abc"
    assert canonical_source_identity("HTTPS://Example.COM/path/") == "https://example.com/path"

    safe_train = [{"source_ids": ["doi:10.1000/a"]}]
    safe_dev = [{"source_ids": ["doi:10.1000/b"]}]
    audit_partitions(safe_train, safe_dev, {"doi:10.1000/c"})

    try:
        audit_partitions(
            [{"source_ids": ["doi:10.1000/ABC"]}],
            [{"source_ids": ["https://doi.org/10.1000/abc"]}],
            set(),
        )
    except ValueError as exc:
        assert "train/dev" in str(exc)
    else:
        raise AssertionError("DOI formatting alias must not bypass train/dev source isolation")

    try:
        audit_partitions(
            [{"source_ids": ["https://doi.org/10.1000/HELD"]}],
            [],
            {"doi:10.1000/held"},
        )
    except ValueError as exc:
        assert "held-out" in str(exc)
    else:
        raise AssertionError("DOI formatting alias must not bypass held-out source isolation")
    print("canonical split source-identity audit self-test: PASS")


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
