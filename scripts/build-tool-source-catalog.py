#!/usr/bin/env python3
"""Build a tool-facing source catalog from one or more external source registries.

Source catalog records remain metadata-only. Inclusion never promotes a source
into a reviewed scientific claim, training example, or held-out benchmark.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA="grow-doc-tool-source-catalog-v1"

def registry_sources(reg: dict) -> list[dict]:
    """Accept list-style registries plus provider-style single-source registries."""
    rows=[]
    if isinstance(reg.get("sources"), list):
        rows.extend(x for x in reg["sources"] if isinstance(x, dict))
    provider=reg.get("provider")
    if isinstance(provider, dict):
        rows.append(provider)
    return rows

def catalog_record(s: dict) -> dict:
    if not s.get("source_id") or not s.get("canonical_url"):
        raise ValueError("source missing stable identity/url")
    rec={k:s.get(k) for k in (
        "source_id","organization","title","source_type","canonical_url","api_base",
        "persistent_ids","retrieval_topics","evidence_tier","rights_status",
        "volatile_fields","notes"
    ) if s.get(k) is not None}
    rec.update({
        "catalog_only":True,
        "scientific_claim_reviewed":False,
        "rag_claim_eligible":False,
        "weight_training_eligible":False,
        "heldout_eligible":False,
    })
    rec["record_sha256"]=hashlib.sha256(
        json.dumps(rec,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return rec

def build(registries: list[dict]) -> dict:
    by_id={}
    for reg in registries:
        for source in registry_sources(reg):
            rec=catalog_record(source)
            sid=rec["source_id"]
            previous=by_id.get(sid)
            if previous and previous != rec:
                raise ValueError(f"conflicting duplicate source_id: {sid}")
            by_id[sid]=rec
    if not by_id:
        raise ValueError("no source records found")
    out=sorted(by_id.values(),key=lambda x:x["source_id"])
    return {
        "schema_version":SCHEMA,
        "policy":{
            "catalog_only":True,
            "claim_promotion_requires_review":True,
            "weight_training_default":False,
            "heldout_default":False,
        },
        "sources":out,
    }

def self_test():
    a={"sources":[{"source_id":"s1","canonical_url":"https://example.org","rag_eligible":True}]}
    b={"provider":{"source_id":"s2","canonical_url":"https://example.net","rag_eligible":True}}
    r=build([a,b])
    assert [x["source_id"] for x in r["sources"]]==["s1","s2"]
    assert all(x["catalog_only"] for x in r["sources"])
    assert all(not x["rag_claim_eligible"] for x in r["sources"])
    assert all(not x["scientific_claim_reviewed"] for x in r["sources"])
    assert all(not x["weight_training_eligible"] for x in r["sources"])
    assert all(not x["heldout_eligible"] for x in r["sources"])
    try:
        build([
            {"sources":[{"source_id":"dup","canonical_url":"https://a.example"}]},
            {"sources":[{"source_id":"dup","canonical_url":"https://b.example"}]},
        ])
        raise AssertionError("conflicting duplicate source accepted")
    except ValueError:
        pass
    print("tool source catalog self-test: PASS")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",type=Path,action="append")
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:
        self_test(); return 0
    if not a.registry or not a.output:
        ap.error("at least one --registry and --output required")
    registries=[json.loads(p.read_text(encoding="utf-8")) for p in a.registry]
    o=build(registries)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
