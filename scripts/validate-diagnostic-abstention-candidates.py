#!/usr/bin/env python3
"""Validate development-only diagnostic abstention challenges and protect held-out isolation."""
from __future__ import annotations
import importlib.util,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
CANDIDATES=ROOT/"model_tuning/eval/candidates/diagnostic_abstention_dev_v1.jsonl"
HELDOUT=ROOT/"model_tuning/eval/heldout_v3.jsonl"

def load_module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
EVAL=load_module(ROOT/"scripts/validate-model-eval.py","grow_doc_eval_validator")

def rows(path):
 return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def canon(value):
 return EVAL.canonical_source_id(str(value or ""))

def validate():
 errors=EVAL.validate(CANDIDATES,require_all_categories=False)
 candidates=rows(CANDIDATES); heldout=rows(HELDOUT)
 heldout_cites={canon(c) for r in heldout for c in (r.get("must_cite") or [])}
 heldout_prompts={str(r.get("prompt","")).strip() for r in heldout}
 seen_sources=set()
 for r in candidates:
  rid=r.get("id","<missing>")
  if r.get("candidate_status")!="development_only":errors.append(f"{rid}: candidate_status must be development_only")
  if r.get("promotion_eligible") is not False:errors.append(f"{rid}: promotion_eligible must be false")
  if r.get("rag_first") is not True:errors.append(f"{rid}: rag_first must be true")
  prompt=str(r.get("prompt","")).strip()
  if prompt in heldout_prompts:errors.append(f"{rid}: prompt duplicates frozen heldout")
  overlap={canon(c) for c in (r.get("must_cite") or [])}&heldout_cites
  if overlap:errors.append(f"{rid}: citation overlaps frozen heldout: {sorted(overlap)}")
  source=(r.get("source_metadata") or {}).get("source_id")
  if source:seen_sources.add(source)
 if len(candidates)<3:errors.append("at least three abstention challenges required")
 if len(seen_sources)<3:errors.append("abstention challenges must use at least three distinct sources")
 return errors

def self_test():
 errors=validate()
 if errors:raise AssertionError(errors)
 print("diagnostic abstention candidate self-test: PASS")

def main():
 errors=validate()
 print(json.dumps({"ok":not errors,"candidate_count":len(rows(CANDIDATES)),"errors":errors},indent=2))
 return 0 if not errors else 2

if __name__=="__main__":raise SystemExit(main())
