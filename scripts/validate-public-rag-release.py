#!/usr/bin/env python3
"""Require the same-origin public RAG release mirror to exactly match the reviewed generated artifact."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
canonical=ROOT/"dataset/generated/tool_data/rag_claims_v1.json";public=ROOT/"public/data/rag_claims_v1.json"
a=canonical.read_bytes();b=public.read_bytes()
assert a==b,"public RAG artifact is not byte-identical to canonical generated artifact"
doc=json.loads(b);assert doc.get("schema_version")=="grow-doc-rag-claims-published-v1"
assert len(doc.get("claims",[]))>0
print(f"public RAG release mirror: PASS sha256={hashlib.sha256(b).hexdigest()} claims={len(doc['claims'])}")
