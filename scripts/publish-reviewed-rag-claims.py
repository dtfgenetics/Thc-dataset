#!/usr/bin/env python3
"""Publish only reviewed, derived-RAG-eligible claims into a deterministic tool artifact."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
SCHEMA="grow-doc-rag-claims-published-v1"
def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def publish(claims_doc:dict,catalog_doc:dict,relationships_doc:dict|None=None)->dict:
 relationship_aware=relationships_doc is not None
 relationships_doc=relationships_doc or {"relationships":[]}
 approved=[r for r in relationships_doc.get("relationships",[]) if r.get("review_state")=="approved"]
 superseded={r.get("right_claim_sha256") for r in approved if r.get("relationship")=="supersedes"}
 related={}
 for r in approved:
  for side,other in (("left_claim_sha256","right_claim_sha256"),("right_claim_sha256","left_claim_sha256")):
   key=r.get(side)
   if key:
    related.setdefault(key,[]).append({"relationship_id":r.get("relationship_id"),"relationship":r.get("relationship"),"related_claim_sha256":r.get(other),"scope_comparison":r.get("scope_comparison"),"evidence":r.get("evidence")})
 known={x.get("source_id") for x in catalog_doc.get("sources",[])}
 rows=[]
 for c in claims_doc.get("claims",[]):
  if c.get("rag_eligible") is not True:continue
  if c.get("claim_sha256") in superseded:continue
  if c.get("weight_training_eligible") is not False:raise ValueError("RAG claim cannot be weight-training eligible")
  if c.get("source_id") not in known:raise ValueError("RAG claim source not present in source catalog")
  if c.get("review_state")!="approved" or c.get("citation_verified") is not True:raise ValueError("invalid promoted claim")
  if c.get("rights_state") not in {"reviewed","government_source_reviewed"}:raise ValueError("invalid rights state for promoted claim")
  row={k:c.get(k) for k in ("claim_sha256","source_id","claim","citation_locator","scope","limitations","rights_state")}
  if relationship_aware:
   row["relationships"]=sorted(related.get(c.get("claim_sha256"),[]),key=lambda x:(x["relationship"],x["related_claim_sha256"] or ""))
   row["has_reviewed_conflict"]=any(x["relationship"]=="contradicts" for x in row["relationships"])
  rows.append(row)
 rows.sort(key=lambda x:(x["source_id"],x["claim_sha256"]))
 policy={"reviewed_claims_only":True,"weight_training_eligible":False}
 if relationship_aware:policy.update({"approved_superseded_claims_excluded_from_retrieval":True,"approved_relationships_attached":True})
 return {"schema_version":SCHEMA,"publication_policy":policy,"claims":rows}
def self_test():
 cat={"sources":[{"source_id":"s"}]};base={"claim_sha256":"a"*64,"source_id":"s","claim":"Scoped result.","citation_locator":"p.1","scope":{"population":"x"},"limitations":[],"review_state":"approved","rights_state":"reviewed","citation_verified":True,"weight_training_eligible":False}
 out=publish({"claims":[{**base,"rag_eligible":False},{**base,"claim_sha256":"b"*64,"rag_eligible":True}]},cat)
 assert len(out["claims"])==1 and out["claims"][0]["claim_sha256"]=="b"*64
 rel={"relationships":[{"relationship_id":"r","left_claim_sha256":"c"*64,"right_claim_sha256":"b"*64,"relationship":"supersedes","review_state":"approved","scope_comparison":{"reason":"newer scoped evidence"},"evidence":[{"source_id":"s","citation_locator":"p.2"}]}]}
 rel_out=publish({"claims":[{**base,"claim_sha256":"b"*64,"rag_eligible":True},{**base,"claim_sha256":"c"*64,"rag_eligible":True}]},cat,rel)
 assert len(rel_out["claims"])==1 and rel_out["claims"][0]["claim_sha256"]=="c"*64
 assert rel_out["publication_policy"]["approved_superseded_claims_excluded_from_retrieval"] is True
 try:publish({"claims":[{**base,"source_id":"unknown","rag_eligible":True}]},cat);raise AssertionError("unknown source published")
 except ValueError:pass
 print("RAG claim publisher self-test: PASS")
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--claims",type=Path);ap.add_argument("--catalog",type=Path);ap.add_argument("--output",type=Path);ap.add_argument("--relationships",type=Path);ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
 if a.self_test:self_test();return 0
 if not a.claims or not a.catalog or not a.output:ap.error("--claims --catalog --output required")
 cb=a.claims.read_bytes();sb=a.catalog.read_bytes();rb=a.relationships.read_bytes() if a.relationships else b'{"relationships":[]}'
 out=publish(json.loads(cb),json.loads(sb),json.loads(rb) if a.relationships else None)
 inputs={"reviewed_claims_sha256":h(cb),"source_catalog_sha256":h(sb)}
 if a.relationships:inputs["claim_relationships_sha256"]=h(rb)
 out["inputs"]=inputs
 raw=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(raw);return 0
if __name__=="__main__":raise SystemExit(main())
