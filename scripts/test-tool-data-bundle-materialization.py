#!/usr/bin/env python3
"""Materialize and validate a synthetic bundle; fixture must never be treated as evidence."""
from __future__ import annotations
import importlib.util,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(n,p):
 s=importlib.util.spec_from_file_location(n,ROOT/p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
builder=load("builder","scripts/build-tool-data-bundle.py");validator=load("validator","scripts/validate-tool-data-bundle.py")
def main():
 src=ROOT/"dataset/fixtures/tool_bundle/germplasm_fixture.json"; data=json.loads(src.read_text())
 assert data["fixture_only"] is True and data["not_scientific_evidence"] is True
 with tempfile.TemporaryDirectory() as d:
  root=Path(d);(root/"germplasm.json").write_bytes(src.read_bytes())
  spec={"bundle_version":"fixture-v1","artifacts":[{"role":"germplasm","path":"germplasm.json","schema_version":data["schema_version"],"rag_eligible":False,"weight_training_eligible":False}]}
  manifest=builder.build(root,spec);assert validator.validate(root,manifest)==[]
  assert manifest["artifacts"][0]["rag_eligible"] is False
 print("synthetic tool bundle materialization: PASS")
if __name__=="__main__":main()
