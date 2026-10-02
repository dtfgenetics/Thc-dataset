#!/usr/bin/env python3
"""Normalize NCBI BioSample metadata while preserving accession provenance."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA="grow-doc-ncbi-biosample-normalized-v1"
ALIASES={
    "cultivar":"cultivar",\n    "cultivar/accession":"cultivar",
    "cultivar accession":"cultivar",
    "cultivar_accession":"cultivar",
    "breed":"breed",
    "breeding history":"breeding_history",
    "breeding_history":"breeding_history",
    "breeding method":"breeding_method",
    "breeding_method":"breeding_method",
    "collection date":"collection_date",
    "collection_date":"collection_date",
    "geographic location":"geo_loc_name",
    "geo_loc_name":"geo_loc_name",
    "latitude and longitude":"lat_lon",
    "lat_lon":"lat_lon",
    "source material id":"source_material_id",
    "source_material_id":"source_material_id",
    "host genotype":"host_genotype",
    "host_genotype":"host_genotype",
    "light intensity":"light_intensity",
    "light_intensity":"light_intensity",
    "light regimen":"light_regimen",
    "light_regm":"light_regimen",
}

def key(name:str)->str:
    return " ".join(name.strip().lower().replace("-"," ").replace("_"," ").split())

def normalize_attributes(attrs)->dict:
    out={}
    for item in attrs or []:
        if not isinstance(item,dict): continue
        name=item.get("harmonized_name") or item.get("harmonizedName") or item.get("name") or item.get("attribute_name")
        value=item.get("value") or item.get("attribute_value")
        if not name or value in (None,""): continue
        canonical=ALIASES.get(key(str(name)), str(name).strip().lower().replace(" ","_"))
        if canonical in out and out[canonical]!=value:
            existing=out[canonical] if isinstance(out[canonical],list) else [out[canonical]]
            if value not in existing: existing.append(value)
            out[canonical]=existing
        else: out[canonical]=value
    return dict(sorted(out.items()))

def normalize(record:dict, retrieved_at:str)->dict:
    accession=record.get("accession") or record.get("biosample_accession")
    organism=record.get("organism") or {}
    if isinstance(organism,str): organism={"organism_name":organism}
    attrs=normalize_attributes(record.get("attributes"))
    out={
        "schema_version":SCHEMA,
        "biosample_accession":accession,
        "organism_name":organism.get("organism_name") or organism.get("organismName"),
        "tax_id":organism.get("tax_id") or organism.get("taxId"),
        "attributes":attrs,
        "source_provider":"NCBI BioSample",
        "retrieved_at":retrieved_at,
        "source_url":f"https://www.ncbi.nlm.nih.gov/biosample/{accession}" if accession else None,
    }
    canonical=json.dumps({k:v for k,v in out.items() if k not in {"retrieved_at","record_sha256"}},sort_keys=True,separators=(",",":")).encode()
    out["record_sha256"]=hashlib.sha256(canonical).hexdigest()
    return out

def validate(out:dict)->list[str]:
    e=[]
    if not str(out.get("biosample_accession") or "").startswith(("SAMN","SAMEA","SAMD")): e.append("invalid or missing BioSample accession")
    if not out.get("organism_name"): e.append("missing organism_name")
    if not out.get("tax_id"): e.append("missing tax_id")
    return e

def self_test():
    fixture={"accession":"SAMN12345678","organism":{"organism_name":"Cannabis sativa","tax_id":3483},"attributes":[{"name":"cultivar/accession","value":"Example A"},{"name":"collection date","value":"2024-07-01"},{"name":"host genotype","value":"XX"}]}
    a=normalize(fixture,"2026-01-01T00:00:00Z"); b=normalize(fixture,"2026-01-01T00:00:00Z")
    assert a==b and not validate(a)
    assert a["attributes"]["cultivar"]=="Example A"
    assert a["attributes"]["collection_date"]=="2024-07-01"
    assert a["attributes"]["host_genotype"]=="XX"
    assert len(a["record_sha256"])==64
    print("NCBI BioSample normalizer self-test: PASS")

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path); ap.add_argument("--output",type=Path); ap.add_argument("--retrieved-at"); ap.add_argument("--self-test",action="store_true"); args=ap.parse_args()
    if args.self_test: self_test(); return 0
    if not args.input or not args.output or not args.retrieved_at: ap.error("--input, --output, and --retrieved-at are required")
    record=json.loads(args.input.read_text(encoding="utf-8")); out=normalize(record,args.retrieved_at); errors=validate(out)
    if errors:
        print("\n".join("ERROR: "+x for x in errors)); return 1
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(f"normalized {out['biosample_accession']}"); return 0

if __name__=="__main__": raise SystemExit(main())
