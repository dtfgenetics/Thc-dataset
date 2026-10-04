#!/usr/bin/env python3
"""Build a deterministic manifest for Grow Doc tool-facing data artifacts."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA="grow-doc-tool-data-bundle-v1"
ALLOWED_ROLES={"source_catalog","chemistry","germplasm","identity_graph","brapi_germplasm","rag_claims","phenotypes","traits","observations","variants","research_evidence"}
def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
def build(root:Path,spec:dict)->dict:
    artifacts=[]
    for a in spec.get("artifacts",[]):
        role=a.get("role"); rel=a.get("path")
        if role not in ALLOWED_ROLES: raise ValueError(f"unsupported artifact role: {role}")
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts: raise ValueError(f"unsafe artifact path: {rel}")
        p=root/rel
        if not p.is_file(): raise ValueError(f"missing artifact: {rel}")
        artifacts.append({"role":role,"path":rel,"schema_version":a.get("schema_version"),"sha256":sha(p),
          "rag_eligible":bool(a.get("rag_eligible",False)),"weight_training_eligible":bool(a.get("weight_training_eligible",False))})
    artifacts.sort(key=lambda x:(x["role"],x["path"]))
    return {"schema_version":SCHEMA,"bundle_version":str(spec.get("bundle_version","1")),
      "policy":{"rag_first":True,"default_weight_training_eligible":False,"stable_identity_required":True},
      "artifacts":artifacts}
def self_test(tmp:Path):
    tmp.mkdir(parents=True,exist_ok=True); (tmp/"g.json").write_text('{"records":[]}\n',encoding="utf-8")
    m=build(tmp,{"bundle_version":"1","artifacts":[{"role":"germplasm","path":"g.json","schema_version":"test","rag_eligible":True}]})
    assert m["policy"]["rag_first"] and not m["artifacts"][0]["weight_training_eligible"]
    research=build(tmp,{"bundle_version":"1","artifacts":[{"role":"research_evidence","path":"g.json","schema_version":"research-claims-v1","rag_eligible":True,"weight_training_eligible":False}]})
    assert research["artifacts"][0]["role"]=="research_evidence"
    assert len(m["artifacts"][0]["sha256"])==64
    try: build(tmp,{"artifacts":[{"role":"germplasm","path":"../x"}]}); raise AssertionError("unsafe path accepted")
    except ValueError: pass
    print("tool data bundle manifest self-test: PASS")
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path); ap.add_argument("--spec",type=Path); ap.add_argument("--output",type=Path); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    if a.self_test:
        import tempfile
        with tempfile.TemporaryDirectory() as d:self_test(Path(d))
        return 0
    if not a.root or not a.spec or not a.output: ap.error("--root --spec --output required")
    m=build(a.root,json.loads(a.spec.read_text(encoding="utf-8"))); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(m,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return 0
if __name__=="__main__": raise SystemExit(main())
