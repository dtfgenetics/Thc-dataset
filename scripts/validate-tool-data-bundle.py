#!/usr/bin/env python3
"""Validate a Grow Doc tool-data bundle before any consumer loads its artifacts."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
SCHEMA="grow-doc-tool-data-bundle-v1"
ROLES={"source_catalog","chemistry","germplasm","identity_graph","brapi_germplasm","rag_claims","phenotypes","traits","observations","variants"}
def digest(p:Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def validate(root:Path,m:dict)->list[str]:
    e=[]
    if m.get("schema_version")!=SCHEMA:e.append("unsupported bundle schema")
    p=m.get("policy") or {}
    if p.get("rag_first") is not True:e.append("bundle must be rag_first")
    if p.get("default_weight_training_eligible") is not False:e.append("bundle must default weight training false")
    if p.get("stable_identity_required") is not True:e.append("bundle must require stable identity")
    seen=set()
    for i,a in enumerate(m.get("artifacts",[])):
        role=a.get("role"); rel=a.get("path"); key=(role,rel)
        if role not in ROLES:e.append(f"artifacts[{i}] unsupported role")
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:e.append(f"artifacts[{i}] unsafe path");continue
        if key in seen:e.append(f"artifacts[{i}] duplicate role/path")
        seen.add(key); fp=root/rel
        if not fp.is_file():e.append(f"artifacts[{i}] missing file");continue
        if digest(fp)!=a.get("sha256"):e.append(f"artifacts[{i}] sha256 mismatch")
        if a.get("weight_training_eligible") is not False:e.append(f"artifacts[{i}] weight training must remain false in tool bundle")
    return e
def self_test(tmp:Path):
    (tmp/"x.json").write_text("{}\n"); sh=digest(tmp/"x.json")
    m={"schema_version":SCHEMA,"policy":{"rag_first":True,"default_weight_training_eligible":False,"stable_identity_required":True},"artifacts":[{"role":"traits","path":"x.json","sha256":sh,"weight_training_eligible":False}]}
    assert validate(tmp,m)==[]
    m["artifacts"][0]["sha256"]="0"*64;assert "sha256 mismatch" in validate(tmp,m)[0]
    print("tool data bundle consumer self-test: PASS")
def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path);ap.add_argument("--manifest",type=Path);ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
    if a.self_test:
        import tempfile
        with tempfile.TemporaryDirectory() as d:self_test(Path(d))
        return 0
    if not a.root or not a.manifest:ap.error("--root and --manifest required")
    errs=validate(a.root,json.loads(a.manifest.read_text()))
    if errs:
        print("\n".join("ERROR: "+x for x in errs));return 1
    print("tool data bundle: PASS");return 0
if __name__=="__main__":raise SystemExit(main())
