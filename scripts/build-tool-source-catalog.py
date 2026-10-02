#!/usr/bin/env python3
"""Build tool-facing source catalog metadata without promoting source records into scientific claims."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
SCHEMA="grow-doc-tool-source-catalog-v1"
def build(reg:dict)->dict:
 out=[]
 for s in reg.get("sources",[]):
  if not s.get("source_id") or not s.get("canonical_url"): raise ValueError("source missing stable identity/url")
  rec={k:s.get(k) for k in ("source_id","organization","title","source_type","canonical_url","persistent_ids","retrieval_topics","evidence_tier","rights_status","volatile_fields") if s.get(k) is not None}
  rec.update({"catalog_only":True,"scientific_claim_reviewed":False,"rag_claim_eligible":False,"weight_training_eligible":False})
  rec["record_sha256"]=hashlib.sha256(json.dumps(rec,sort_keys=True,separators=(",",":")).encode()).hexdigest();out.append(rec)
 out.sort(key=lambda x:x["source_id"])
 return {"schema_version":SCHEMA,"policy":{"catalog_only":True,"claim_promotion_requires_review":True,"weight_training_default":False},"sources":out}
def self_test():
 r=build({"sources":[{"source_id":"s","canonical_url":"https://example.org","rag_eligible":True}]});x=r["sources"][0]
 assert x["catalog_only"] and not x["rag_claim_eligible"] and not x["scientific_claim_reviewed"] and not x["weight_training_eligible"]
 print("tool source catalog self-test: PASS")
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--registry",type=Path);ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
 if a.self_test:self_test();return 0
 if not a.registry or not a.output:ap.error("--registry and --output required")
 o=build(json.loads(a.registry.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n");return 0
if __name__=="__main__":raise SystemExit(main())
