#!/usr/bin/env python3
"""Verify committed production RAG artifact is exactly reproducible from reviewed inputs."""
from __future__ import annotations
import importlib.util,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def h(b):return hashlib.sha256(b).hexdigest()
spec=importlib.util.spec_from_file_location("pub",ROOT/"scripts/publish-reviewed-rag-claims.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
claims=ROOT/"dataset/reviewed/cornell_reviewed_claims_v1.json";catalog=ROOT/"dataset/generated/tool_data/source_catalog_v1.json";relationships=ROOT/"dataset/reviewed/claim_relationships_v1.json";published=ROOT/"dataset/generated/tool_data/rag_claims_v1.json"
cb=claims.read_bytes();sb=catalog.read_bytes();rb=relationships.read_bytes()
expected=m.publish(json.loads(cb),json.loads(sb),json.loads(rb));expected["inputs"]={"reviewed_claims_sha256":h(cb),"source_catalog_sha256":h(sb),"claim_relationships_sha256":h(rb)}
actual=json.loads(published.read_text())
assert actual==expected,"committed RAG artifact differs from deterministic publisher output"
assert len(actual["claims"])>0,"production RAG artifact must not be empty"
assert all(c["source_id"] for c in actual["claims"])
assert all("relationships" in c and "has_reviewed_conflict" in c for c in actual["claims"])
print(f"production RAG artifact: PASS ({len(actual['claims'])} reviewed claim(s))")
