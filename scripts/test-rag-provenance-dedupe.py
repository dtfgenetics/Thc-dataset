#!/usr/bin/env python3
"""Regression test for canonical RAG provenance consolidation."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("grow_doc_corpus_builder", SCRIPTS / "build-model-corpus.py")
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def row(source_id: str, profile_id: str) -> dict:
    claim = "A synthetic claim used only to verify provenance consolidation."
    source = {
        "source_id": source_id,
        "title": "Synthetic source",
        "organization": "Grow Doc test",
        "publisher": None,
        "authors": [],
        "publicationDate": None,
        "year": None,
        "accessedDate": None,
        "doi": None,
        "url": None,
    }
    return {
        "id": f"rag-{profile_id}",
        "profile_id": profile_id,
        "profile_ids": [profile_id],
        "profile_name": "Synthetic",
        "category": "test",
        "claim": claim,
        "claim_sha256": builder.sha(builder.norm(claim)),
        "source_id": source_id,
        "source_ids": [source_id],
        "source": source,
        "sources": [source],
        "review_status": "reviewed",
        "retrieval_only": True,
    }


primary = "doi:10.1234/growdoc.synthetic"
alias = "url:https://doi.org/10.1234/GROWDOC.SYNTHETIC"
merged, duplicate_claims, merged_links = builder.dedupe_rag([
    row(primary, "profile-a"),
    row(alias, "profile-b"),
])

assert duplicate_claims == 1
assert len(merged) == 1
result = merged[0]
assert result["source_ids"] == [primary], "one paper alias must count as one independent source"
assert result["source_alias_ids"] == [alias], "raw alias identifier must be preserved"
assert len(result["sources"]) == 1, "canonical duplicate source record must not inflate corroboration"
assert len(result["source_aliases"]) == 1, "full alias metadata must be retained"
assert result["source_aliases"][0]["source_id"] == alias
assert result["profile_ids"] == ["profile-a", "profile-b"]
assert len(builder.canonical_sources(result["source_ids"])) == 1
assert merged_links >= 2, "profile and alias provenance should both remain traceable"

print("RAG provenance dedupe regression: PASS")
