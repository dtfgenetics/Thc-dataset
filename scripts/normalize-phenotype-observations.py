#!/usr/bin/env python3
"""Normalize provenance-preserving phenotype/trait observations for shared Grow Doc tools."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
SCHEMA="grow-doc-phenotype-observation-v1"
IDENTITY_KEYS=("grin_accession","biosample_accession","brapi_germplasm_db_id")
def s(v): return str(v).strip() if v is not None else ""
def normalize(r:dict)->dict:
    identity=next(((k,s(r.get(k))) for k in IDENTITY_KEYS if s(r.get(k))),None)
    if not identity: raise ValueError("observation missing stable germplasm identity")
    trait_id=s(r.get("trait_id") or r.get("ontology_term"))
    if not trait_id: raise ValueError("observation missing trait_id/ontology_term")
    source_id=s(r.get("source_id"))
    if not source_id: raise ValueError("observation missing source_id")
    value=r.get("value")
    if value is None or value=="": raise ValueError("observation missing value")
    numeric=isinstance(value,(int,float)) and not isinstance(value,bool)
    unit=s(r.get("unit"))
    if numeric and not unit: raise ValueError("numeric observation missing unit")
    rec={"schema_version":SCHEMA,identity[0]:identity[1],"trait_id":trait_id,"value":value,
      "unit":unit or None,"source_id":source_id,"citation":s(r.get("citation")) or None,
      "environment":r.get("environment") or {},"treatment":r.get("treatment") or {},
      "method":s(r.get("method")) or None,"observed_at":s(r.get("observed_at")) or None,
      "evidence_tier":s(r.get("evidence_tier")) or "unreviewed",
      "review_state":s(r.get("review_state")) or "pending",
      "rag_eligible":bool(r.get("rag_eligible",False)),"weight_training_eligible":False}
    stable=json.dumps(rec,sort_keys=True,separators=(",",":")).encode(); rec["record_sha256"]=hashlib.sha256(stable).hexdigest()
    return rec
def self_test():
    r=normalize({"grin_accession":"PI 1","trait_id":"CO:trait","value":12.5,"unit":"cm","source_id":"study:1","environment":{"location":"trial"}})
    assert r["unit"]=="cm" and r["weight_training_eligible"] is False and r["environment"]["location"]=="trial"
    for bad in ({"trait_id":"t","value":1,"unit":"cm","source_id":"s"},{"grin_accession":"PI 1","value":1,"unit":"cm","source_id":"s"},{"grin_accession":"PI 1","trait_id":"t","value":1,"unit":"cm"},{"grin_accession":"PI 1","trait_id":"t","value":1,"source_id":"s"}):
        try: normalize(bad); raise AssertionError("invalid observation accepted")
        except ValueError: pass
    print("phenotype observation normalizer self-test: PASS")
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path); ap.add_argument("--output",type=Path); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    if a.self_test:self_test(); return 0
    if not a.input or not a.output:ap.error("--input and --output required")
    d=json.loads(a.input.read_text()); rows=d if isinstance(d,list) else d.get("records",[])
    out=[normalize(x) for x in rows]; out.sort(key=lambda x:(x.get("grin_accession",""),x.get("biosample_accession",""),x["trait_id"],x["record_sha256"]))
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps({"schema_version":SCHEMA,"records":out},indent=2,sort_keys=True)+"\n"); return 0
if __name__=="__main__":raise SystemExit(main())
