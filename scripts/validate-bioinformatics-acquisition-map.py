#!/usr/bin/env python3
"""Validate the Grow Doc bioinformatics acquisition map."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

PATH = Path("dataset/sources/bioinformatics_acquisition_map_v1.json")
REQUIRED = {"resource_id","provider","kind","content","canonical_url","rag_eligible","weight_training_eligible"}

def validate(data: dict) -> list[str]:
    errors=[]
    p=data.get("policy") or {}
    if p.get("rag_first") is not True: errors.append("rag_first must be true")
    if p.get("preserve_accessions") is not True: errors.append("preserve_accessions must be true")
    if p.get("preserve_source_citations") is not True: errors.append("preserve_source_citations must be true")
    rows=data.get("resources")
    if not isinstance(rows,list) or not rows: return errors+["resources must be non-empty"]
    seen=set()
    for i,row in enumerate(rows):
        miss=sorted(REQUIRED-set(row))
        if miss: errors.append(f"resources[{i}] missing: {', '.join(miss)}"); continue
        rid=str(row["resource_id"]).strip()
        if not rid or rid in seen: errors.append(f"duplicate/empty resource_id: {rid!r}")
        seen.add(rid)
        u=urlparse(str(row["canonical_url"]))
        if u.scheme!="https" or not u.netloc: errors.append(f"{rid}: canonical_url must be HTTPS")
        if row["weight_training_eligible"] is not False: errors.append(f"{rid}: acquisition resources must not default into weights")
        if not isinstance(row["content"],list) or not row["content"]: errors.append(f"{rid}: content must be non-empty")
        if row.get("kind") in {"bioproject","refseq_bioproject"} and not row.get("accession"):
            errors.append(f"{rid}: NCBI project requires accession")
    return errors

def main()->int:
    data=json.loads(PATH.read_text(encoding="utf-8"))
    errors=validate(data)
    if errors:
        print("\n".join("ERROR: "+x for x in errors)); return 1
    print(f"bioinformatics acquisition map: PASS ({len(data['resources'])} resources)")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
