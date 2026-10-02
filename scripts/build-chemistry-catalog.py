#!/usr/bin/env python3
"""Materialize a tool-facing chemistry identity catalog from the reviewed PubChem seed registry."""
from __future__ import annotations
import argparse, json
from pathlib import Path

SCHEMA="grow-doc-chemistry-catalog-v1"

def build(reg:dict)->dict:
    provider=reg.get("provider") or {}
    rows=[]
    for c in reg.get("seed_compounds",[]):
        cid=c.get("cid")
        if not isinstance(cid,int) or cid<=0: raise ValueError("invalid PubChem CID")
        if c.get("compound_id")!=f"pubchem:{cid}": raise ValueError(f"CID {cid}: unstable compound_id")
        rows.append({
            "compound_id":c["compound_id"],
            "provider":"PubChem",
            "provider_id":str(cid),
            "preferred_name":c.get("preferred_name"),
            "aliases":c.get("aliases") or [],
            "class":c.get("class"),
            "canonical_url":c.get("canonical_url"),
            "source_id":provider.get("source_id"),
            "identity_scope":"chemical_identity_only",
            "properties_status":"fetch_with_collect_pubchem_compound",
            "rag_eligible":True,
            "weight_training_eligible":False,
            "heldout_eligible":False
        })
    rows.sort(key=lambda x:int(x["provider_id"]))
    if not rows: raise ValueError("chemistry registry produced no compounds")
    return {
        "schema_version":SCHEMA,
        "policy":{
            "canonical_provider":"PubChem",
            "stable_identity":"CID",
            "database_identity_is_not_effect_evidence":True,
            "weight_training_default":False,
            "heldout_default":False
        },
        "compounds":rows
    }

def self_test():
    r=build({"provider":{"source_id":"pubchem_pug_rest"},"seed_compounds":[{"compound_id":"pubchem:1","cid":1,"preferred_name":"x","aliases":[],"class":"test","canonical_url":"https://pubchem.ncbi.nlm.nih.gov/compound/1"}]})
    assert r["compounds"][0]["provider_id"]=="1"
    assert r["compounds"][0]["identity_scope"]=="chemical_identity_only"
    assert r["compounds"][0]["weight_training_eligible"] is False
    print("chemistry catalog self-test: PASS")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test: self_test(); return 0
    if not a.registry or not a.output: ap.error("--registry and --output required")
    out=build(json.loads(a.registry.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    return 0

if __name__=="__main__": raise SystemExit(main())
