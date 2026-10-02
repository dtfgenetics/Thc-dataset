#!/usr/bin/env python3
"""Resolve bioinformatics identities without unsafe cultivar-name joins."""
from __future__ import annotations
import argparse, json
from pathlib import Path

SCHEMA="grow-doc-bioinformatics-identity-graph-v1"
STABLE={"grin_accession","biosample_accession","bioproject_accession","assembly_accession","brapi_germplasm_db_id"}

def build(records:list[dict])->dict:
    nodes={}; edges=[]; errors=[]
    for i,r in enumerate(records):
        ids={k:str(r[k]).strip() for k in STABLE if r.get(k)}
        if not ids:
            errors.append(f"records[{i}] has no stable identity")
            continue
        for kind,value in sorted(ids.items()):
            nid=f"{kind}:{value}"
            nodes[nid]={"id":nid,"kind":kind,"value":value}
        keys=sorted(f"{k}:{v}" for k,v in ids.items())
        anchor=keys[0]
        for other in keys[1:]:
            edges.append({"from":anchor,"to":other,"relationship":"same_source_record","evidence":"explicit_accession"})
        if r.get("cultivar_name"):
            nodes[anchor].setdefault("display_names",[])
            if r["cultivar_name"] not in nodes[anchor]["display_names"]: nodes[anchor]["display_names"].append(r["cultivar_name"])
    edges.sort(key=lambda x:(x["from"],x["to"]))
    return {"schema_version":SCHEMA,"nodes":[nodes[k] for k in sorted(nodes)],"edges":edges,"errors":errors,
            "policy":{"cultivar_name_is_identity":False,"stable_accession_required":True,"ambiguous_name_join":"forbidden"}}

def self_test():
    rows=[
      {"biosample_accession":"SAMN1","bioproject_accession":"PRJNA1","cultivar_name":"Same Name"},
      {"biosample_accession":"SAMN2","bioproject_accession":"PRJNA2","cultivar_name":"Same Name"},
    ]
    g=build(rows)
    assert not g["errors"]
    assert len(g["nodes"])==4 and len(g["edges"])==2
    assert all(e["evidence"]=="explicit_accession" for e in g["edges"])
    # Same display name must not collapse distinct accessions.
    assert len([n for n in g["nodes"] if n["kind"]=="biosample_accession"])==2
    bad=build([{"cultivar_name":"Blue Example"}])
    assert bad["errors"]==["records[0] has no stable identity"]
    print("bioinformatics identity resolver self-test: PASS")

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path); ap.add_argument("--output",type=Path); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    if a.self_test: self_test(); return 0
    if not a.input or not a.output: ap.error("--input and --output required")
    data=json.loads(a.input.read_text(encoding="utf-8")); rows=data if isinstance(data,list) else data.get("records",[])
    graph=build(rows)
    if graph["errors"]:
        print("\n".join("ERROR: "+e for e in graph["errors"])); return 1
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(graph,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return 0

if __name__=="__main__": raise SystemExit(main())
