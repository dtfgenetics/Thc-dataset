#!/usr/bin/env python3
"""Normalize USDA GRIN germplasm metadata into the Grow Doc identity contract."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA="grow-doc-grin-germplasm-normalized-v1"
DEFAULT_SOURCE_ID="usda_grin_cannabis_sativa_taxon_8862"

def clean(v): return str(v).strip() if v is not None else ""

def canonical_json_sha256(value: dict) -> str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def normalize(r:dict)->dict:
    accession=clean(r.get("accession") or r.get("accessionNumber") or r.get("pi_number"))
    if not accession: raise ValueError("GRIN record missing accession")
    retrieved_at=clean(r.get("retrieved_at") or r.get("retrievedAt"))
    if not retrieved_at: raise ValueError("GRIN record missing retrieval timestamp")
    taxon=clean(r.get("taxon") or r.get("taxonomy") or r.get("scientificName"))
    name=clean(r.get("cultivar") or r.get("name") or r.get("plantName"))
    source_url=clean(r.get("source_url") or r.get("url"))
    source_id=clean(r.get("source_id")) or DEFAULT_SOURCE_ID
    rights_state=clean(r.get("rights_state")) or "review_required"
    if "review" not in rights_state.lower():
        raise ValueError("GRIN record rights_state must remain review-gated")
    rec={
        "schema_version":SCHEMA,
        "grin_accession":accession,
        "cultivar_name":name or None,
        "taxon":taxon or None,
        "source_id":source_id,
        "source_provider":"USDA GRIN-Global",
        "source_url":source_url or None,
        "retrieved_at":retrieved_at,
        "source_record_sha256":canonical_json_sha256(r),
        "rights_state":rights_state,
        "rag_eligible":bool(r.get("rag_eligible",False)),
        "weight_training_eligible":False,
        "heldout_eligible":False,
    }
    stable=json.dumps(rec,sort_keys=True,separators=(",",":")).encode()
    rec["record_sha256"]=hashlib.sha256(stable).hexdigest()
    return rec

def self_test():
    a=normalize({
        "accession":"PI 123456",
        "cultivar":"Example",
        "scientificName":"Cannabis sativa",
        "source_url":"https://npgsweb.ars-grin.gov/",
        "retrieved_at":"2026-10-02T00:00:00Z"
    })
    assert a["grin_accession"]=="PI 123456" and a["cultivar_name"]=="Example"
    assert a["weight_training_eligible"] is False and a["heldout_eligible"] is False
    assert a["rights_state"]=="review_required" and len(a["source_record_sha256"])==64
    for bad in (
        {"cultivar":"name only","retrieved_at":"2026-10-02T00:00:00Z"},
        {"accession":"PI 1"},
        {"accession":"PI 1","retrieved_at":"2026-10-02T00:00:00Z","rights_state":"approved"},
    ):
        try: normalize(bad); raise AssertionError("invalid GRIN record accepted")
        except ValueError: pass
    print("GRIN germplasm normalizer self-test: PASS")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test: self_test(); return 0
    if not a.input or not a.output: ap.error("--input and --output required")
    data=json.loads(a.input.read_text(encoding="utf-8"))
    rows=data if isinstance(data,list) else data.get("records",[])
    out=[normalize(r) for r in rows]
    payload={"schema_version":SCHEMA,"records":sorted(out,key=lambda x:x["grin_accession"])}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return 0

if __name__=="__main__": raise SystemExit(main())
