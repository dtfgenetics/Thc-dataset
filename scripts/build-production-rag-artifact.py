#!/usr/bin/env python3
"""Build the production Grow Doc RAG artifact from every reviewed claim bundle."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCHEMA="grow-doc-reviewed-claim-v1"
def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def load_publisher():
 spec=importlib.util.spec_from_file_location("pub",ROOT/"scripts/publish-reviewed-rag-claims.py")
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def reviewed_paths(reviewed_dir:Path)->list[Path]:
 return sorted(p for p in reviewed_dir.glob("*_reviewed_claims_v1.json") if p.is_file())
def load_combined(paths:list[Path])->tuple[dict,dict]:
 claims=[];hashes={};seen=set()
 for p in paths:
  raw=p.read_bytes();doc=json.loads(raw)
  if doc.get("schema_version")!=SCHEMA:raise ValueError(f"{p}: unexpected schema_version")
  rel=p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()
  hashes[rel]=h(raw)
  for c in doc.get("claims",[]):
   key=c.get("claim_sha256")
   if not key:raise ValueError(f"{p}: claim_sha256 required")
   if key in seen:raise ValueError(f"duplicate reviewed claim_sha256: {key}")
   seen.add(key);claims.append(c)
 return {"schema_version":SCHEMA,"claims":claims},hashes
def canonical_combined(doc:dict)->bytes:
 return (json.dumps(doc,sort_keys=True,separators=(",",":"))+"\n").encode()
def build(reviewed_dir:Path,catalog:Path,relationships:Path)->dict:
 paths=reviewed_paths(reviewed_dir)
 if not paths:raise ValueError("no reviewed claim bundles found")
 combined,_file_hashes=load_combined(paths)
 cb=canonical_combined(combined);sb=catalog.read_bytes();rb=relationships.read_bytes()
 pub=load_publisher()
 out=pub.publish(combined,json.loads(sb),json.loads(rb))
 out["inputs"]={"reviewed_claims_sha256":h(cb),"source_catalog_sha256":h(sb),"claim_relationships_sha256":h(rb)}
 return out
def self_test():
 import tempfile
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);reviewed=root/"reviewed";reviewed.mkdir()
  claim={"claim_sha256":"a"*64,"source_id":"s","claim":"Scoped.","citation_locator":"p.1","scope":{"population":"x"},"limitations":[],"review_state":"approved","rights_state":"reviewed","citation_verified":True,"rag_eligible":True,"weight_training_eligible":False}
  (reviewed/"a_reviewed_claims_v1.json").write_text(json.dumps({"schema_version":SCHEMA,"claims":[claim]}))
  cat=root/"catalog.json";cat.write_text(json.dumps({"sources":[{"source_id":"s"}]}))
  rel=root/"relationships.json";rel.write_text(json.dumps({"relationships":[]}))
  out=build(reviewed,cat,rel)
  assert len(out["claims"])==1 and out["claims"][0]["claim_sha256"]=="a"*64
 print("production RAG builder self-test: PASS")
def main()->int:
 a=argparse.ArgumentParser();a.add_argument("--reviewed-dir",type=Path,default=ROOT/"dataset/reviewed");a.add_argument("--catalog",type=Path,default=ROOT/"dataset/generated/tool_data/source_catalog_v1.json");a.add_argument("--relationships",type=Path,default=ROOT/"dataset/reviewed/claim_relationships_v1.json");a.add_argument("--output",type=Path);a.add_argument("--self-test",action="store_true");x=a.parse_args()
 if x.self_test:self_test();return 0
 if not x.output:a.error("--output required")
 out=build(x.reviewed_dir,x.catalog,x.relationships);x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n");return 0
if __name__=="__main__":raise SystemExit(main())
