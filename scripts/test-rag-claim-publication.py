#!/usr/bin/env python3
"""Ensure pending fixture claims publish as an empty RAG artifact."""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("pub",ROOT/"scripts/publish-reviewed-rag-claims.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def main():
 claims=json.loads((ROOT/"dataset/fixtures/tool_bundle/reviewed_claims_fixture.json").read_text())
 cat=json.loads((ROOT/"dataset/generated/tool_data/source_catalog_v1.json").read_text())
 out=m.publish(claims,cat);assert out["claims"]==[]
 print("pending claims excluded from RAG publication: PASS")
if __name__=="__main__":main()
