#!/usr/bin/env python3
"""Verify committed production RAG artifact is exactly reproducible from all reviewed inputs."""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("builder",ROOT/"scripts/build-production-rag-artifact.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
published=ROOT/"dataset/generated/tool_data/rag_claims_v1.json"
expected=m.build(ROOT/"dataset/reviewed",ROOT/"dataset/generated/tool_data/source_catalog_v1.json",ROOT/"dataset/reviewed/claim_relationships_v1.json")
actual=json.loads(published.read_text())
assert actual==expected,"committed RAG artifact differs from deterministic multi-source builder output"
assert len(actual["claims"])>0,"production RAG artifact must not be empty"
assert all(c["source_id"] and c["citation_locator"] and c["scope"] for c in actual["claims"])
assert all("relationships" in c and "has_reviewed_conflict" in c for c in actual["claims"])
print(f"production RAG artifact: PASS ({len(actual['claims'])} reviewed claim(s))")
