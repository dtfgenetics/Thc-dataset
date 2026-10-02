#!/usr/bin/env python3
"""Export normalized Grow Doc germplasm identities as BrAPI-compatible records."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def export(rows:list[dict])->list[dict]:
    out=[]
    for i,r in enumerate(rows):
        gid=r.get("brapi_germplasm_db_id") or r.get("grin_accession") or r.get("biosample_accession")
        if not gid:
            raise ValueError(f"records[{i}] lacks stable germplasm identity")
        accession=r.get("grin_accession") or r.get("biosample_accession") or gid
        external=[]
        for key,source in (("grin_accession","USDA-GRIN"),("biosample_accession","NCBI-BioSample"),("bioproject_accession","NCBI-BioProject"),("assembly_accession","NCBI-Assembly")):
            if r.get(key): external.append({"referenceID":str(r[key]),"referenceSource":source})
        rec={
          "germplasmDbId":str(gid),
          "germplasmName":str(r.get("cultivar_name") or accession),
          "accessionNumber":str(accession),
          "externalReferences":external,
          "additionalInfo":{
            "growDocIdentityPolicy":"stable_accession_required",
            "cultivarNameIsIdentity":False,
          },
        }
        if r.get("pedigree"): rec["pedigree"]=str(r["pedigree"])
        if r.get("seed_source"): rec["seedSource"]=str(r["seed_source"])
        out.append(rec)
    return sorted(out,key=lambda x:x["germplasmDbId"])

def self_test():
    rows=[{"grin_accession":"PI 123","biosample_accession":"SAMN1","cultivar_name":"Example"}]
    a=export(rows); assert a[0]["germplasmDbId"]=="PI 123"
    assert a[0]["germplasmName"]=="Example"
    assert len(a[0]["externalReferences"])==2
    assert a[0]["additionalInfo"]["cultivarNameIsIdentity"] is False
    try: export([{"cultivar_name":"Name only"}]); raise AssertionError("unsafe name-only record accepted")
    except ValueError: pass
    print("BrAPI germplasm exporter self-test: PASS")

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path); ap.add_argument("--output",type=Path); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    if a.self_test: self_test(); return 0
    if not a.input or not a.output: ap.error("--input and --output required")
    data=json.loads(a.input.read_text(encoding="utf-8")); rows=data if isinstance(data,list) else data.get("records",[])
    payload={"metadata":{"datafiles":[],"pagination":{"currentPage":0,"pageSize":len(rows),"totalCount":len(rows),"totalPages":1 if rows else 0},"status":[]},"result":{"data":export(rows)}}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return 0
if __name__=="__main__": raise SystemExit(main())
