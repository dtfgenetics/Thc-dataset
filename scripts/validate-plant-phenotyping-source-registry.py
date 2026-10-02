#!/usr/bin/env python3
"""Validate plant phenotyping/standards source identities."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

PATH=Path("dataset/sources/plant_phenotyping_standards_registry_v1.json")
REQUIRED={"source_id","organization","title","source_type","canonical_url","retrieval_topics","evidence_tier","rag_eligible","weight_training_eligible","heldout_eligible","rights_status"}

def validate(data:dict)->list[str]:
    errors=[]
    p=data.get("policy") or {}
    if p.get("rag_first") is not True: errors.append("rag_first must be true")
    if p.get("weight_training_default") is not False: errors.append("weight_training_default must be false")
    if p.get("heldout_default") is not False: errors.append("heldout_default must be false")
    rows=data.get("sources")
    if not isinstance(rows,list) or not rows: return errors+["sources must be non-empty"]
    seen=set()
    for i,s in enumerate(rows):
        missing=sorted(REQUIRED-set(s))
        if missing: errors.append(f"sources[{i}] missing: {', '.join(missing)}"); continue
        sid=str(s["source_id"]).strip()
        if not sid or sid in seen: errors.append(f"invalid/duplicate source_id: {sid!r}")
        seen.add(sid)
        u=urlparse(str(s["canonical_url"]))
        if u.scheme!="https" or not u.netloc: errors.append(f"{sid}: canonical_url must be HTTPS")
        if s["rag_eligible"] is not True: errors.append(f"{sid}: must be RAG eligible")
        if s["weight_training_eligible"] is not False: errors.append(f"{sid}: weight training must remain false")
        if s["heldout_eligible"] is not False: errors.append(f"{sid}: heldout must remain false")
        if "review" not in str(s["rights_status"]).lower(): errors.append(f"{sid}: rights must remain review-gated")
        if not s["retrieval_topics"]: errors.append(f"{sid}: retrieval_topics cannot be empty")
    return errors

def main()->int:
    d=json.loads(PATH.read_text(encoding="utf-8"))
    e=validate(d)
    if e:
        for x in e: print("ERROR:",x)
        return 1
    print(f"plant phenotyping source registry: PASS ({len(d['sources'])} sources)")
    return 0

if __name__=="__main__": raise SystemExit(main())
