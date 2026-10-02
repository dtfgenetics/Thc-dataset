#!/usr/bin/env python3
"""Resolve reviewed trait aliases and normalize compatible measurement units."""
from __future__ import annotations
import argparse,json
from pathlib import Path

UNIT_MAP={
 "length":{"mm":("mm",1.0),"cm":("mm",10.0),"m":("mm",1000.0)},
 "mass":{"mg":("mg",1.0),"g":("mg",1000.0),"kg":("mg",1000000.0)},
 "time":{"s":("s",1.0),"min":("s",60.0),"h":("s",3600.0),"day":("s",86400.0)},
}
def load_registry(path:Path)->dict:
    d=json.loads(path.read_text(encoding="utf-8")); out={}
    for t in d.get("traits",[]):
        tid=str(t.get("trait_id","")).strip()
        if not tid or not t.get("reviewed",False): continue
        for a in [t.get("preferred_name"),*(t.get("aliases") or [])]:
            if a: out[str(a).strip().lower()]={"trait_id":tid,"preferred_name":t.get("preferred_name"),"ontology":t.get("ontology")}
    return out
def resolve(name:str,registry:dict)->dict:
    hit=registry.get(str(name).strip().lower())
    if not hit: raise ValueError(f"unreviewed/unresolved trait: {name}")
    return dict(hit)
def normalize_unit(value,unit:str,dimension:str)->dict:
    if dimension not in UNIT_MAP or unit not in UNIT_MAP[dimension]: raise ValueError(f"unsupported unit/dimension: {unit}/{dimension}")
    canonical,factor=UNIT_MAP[dimension][unit]
    return {"value":value,"unit":unit,"canonical_value":float(value)*factor,"canonical_unit":canonical,"dimension":dimension}
def self_test(tmp:Path):
    p=tmp/"r.json"; p.write_text(json.dumps({"traits":[{"trait_id":"CO:test:1","preferred_name":"Plant height","aliases":["height"],"ontology":"Crop Ontology","reviewed":True},{"trait_id":"x","preferred_name":"Secret","reviewed":False}]}))
    r=load_registry(p); assert resolve("HEIGHT",r)["trait_id"]=="CO:test:1"
    assert normalize_unit(12.5,"cm","length")["canonical_value"]==125.0
    for fn in (lambda:resolve("Secret",r),lambda:normalize_unit(1,"ppm","length")):
        try:fn(); raise AssertionError("unsafe mapping accepted")
        except ValueError:pass
    print("trait ontology/unit resolver self-test: PASS")
def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--registry",type=Path);ap.add_argument("--trait");ap.add_argument("--value",type=float);ap.add_argument("--unit");ap.add_argument("--dimension");ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
    if a.self_test:
        import tempfile
        with tempfile.TemporaryDirectory() as d:self_test(Path(d))
        return 0
    if not a.registry or not a.trait:ap.error("--registry and --trait required")
    out=resolve(a.trait,load_registry(a.registry))
    if a.value is not None:
        if not a.unit or not a.dimension:ap.error("--unit and --dimension required with --value")
        out["measurement"]=normalize_unit(a.value,a.unit,a.dimension)
    print(json.dumps(out,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
