#!/usr/bin/env python3
"""Build deterministic NCBI genome/BioProject metadata manifests for Grow Doc.

The collector is metadata-first: it consumes NCBI Datasets JSON/JSONL supplied
via --input or, with --fetch, invokes the official datasets CLI. It never
downloads sequence data.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

SCHEMA="grow-doc-ncbi-genome-metadata-manifest-v1"

def _lines(text:str):
    text=text.strip()
    if not text: return []
    try:
        obj=json.loads(text)
        if isinstance(obj,dict) and isinstance(obj.get("reports"),list): return obj["reports"]
        if isinstance(obj,list): return obj
        return [obj]
    except json.JSONDecodeError:
        return [json.loads(x) for x in text.splitlines() if x.strip()]

def normalize(reports:list[dict], query_accession:str, retrieved_at:str)->dict:
    records=[]
    for report in reports:
        accession=report.get("accession") or report.get("assemblyInfo",{}).get("assemblyAccession")
        organism=report.get("organism") or {}
        org_name=organism.get("organismName") if isinstance(organism,dict) else None
        tax_id=organism.get("taxId") if isinstance(organism,dict) else None
        bioprojects=report.get("assemblyInfo",{}).get("bioprojectAccession")
        if isinstance(bioprojects,str): bioprojects=[bioprojects]
        records.append({
            "assembly_accession": accession,
            "organism_name": org_name,
            "tax_id": tax_id,
            "bioproject_accessions": bioprojects or [],
            "source_provider": "NCBI",
            "source_query_accession": query_accession,
        })
    records.sort(key=lambda x:(x["assembly_accession"] or "",x["organism_name"] or ""))
    payload={
        "schema_version":SCHEMA,
        "source_provider":"NCBI Datasets",
        "source_query_accession":query_accession,
        "retrieved_at":retrieved_at,
        "sequence_downloaded":False,
        "records":records,
    }
    canonical=json.dumps(payload["records"],sort_keys=True,separators=(",",":")).encode()
    payload["records_sha256"]=hashlib.sha256(canonical).hexdigest()
    return payload

def fetch(accession:str)->str:
    cmd=["datasets","summary","genome","accession",accession,"--as-json-lines"]
    p=subprocess.run(cmd,check=True,capture_output=True,text=True)
    return p.stdout

def self_test()->None:
    fixture={"reports":[{"accession":"GCF_000000001.1","organism":{"organismName":"Cannabis sativa","taxId":3483},"assemblyInfo":{"bioprojectAccession":"PRJNA1"}}]}
    a=normalize(fixture["reports"],"PRJNA1","2026-01-01T00:00:00Z")
    b=normalize(fixture["reports"],"PRJNA1","2026-01-01T00:00:00Z")
    assert a==b
    assert a["sequence_downloaded"] is False
    assert a["records"][0]["tax_id"]==3483
    assert a["records"][0]["bioproject_accessions"]==["PRJNA1"]
    assert len(a["records_sha256"])==64
    print("NCBI metadata collector self-test: PASS")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--accession")
    ap.add_argument("--input",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--fetch",action="store_true")
    ap.add_argument("--retrieved-at")
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test: self_test(); return 0
    if not args.accession or not args.output: ap.error("--accession and --output are required")
    if args.fetch == bool(args.input): ap.error("choose exactly one of --fetch or --input")
    raw=fetch(args.accession) if args.fetch else args.input.read_text(encoding="utf-8")
    stamp=args.retrieved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    manifest=normalize(_lines(raw),args.accession,stamp)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"wrote {len(manifest['records'])} NCBI metadata records to {args.output}")
    return 0

if __name__=="__main__": raise SystemExit(main())
