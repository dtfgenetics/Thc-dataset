#!/usr/bin/env python3
"""Validate reviewed-claim support, qualification, contradiction and supersession links."""
from __future__ import annotations
import argparse,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
KINDS={"supports","qualifies","contradicts","supersedes"}
def load(p):return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
def claims():
 out={}
 for p in (ROOT/"dataset/reviewed").glob("*.json"):
  if p.name.startswith("claim_relationships"):continue
  for r in load(p).get("claims",[]):
   h=r.get("claim_sha256")
   if h:out[h]=r
 return out
def validate(rows,known=None):
 known=known or claims();e=[];ids=set();pairs=set()
 for i,r in enumerate(rows,1):
  rid=str(r.get("relationship_id",""));left=r.get("left_claim_sha256");right=r.get("right_claim_sha256");kind=r.get("relationship")
  if not rid:e.append(f"row {i}: relationship_id required")
  elif rid in ids:e.append(f"duplicate relationship_id: {rid}")
  ids.add(rid)
  if left==right:e.append(f"{rid}: relationship cannot self-reference")
  if left not in known:e.append(f"{rid}: unknown left claim")
  if right not in known:e.append(f"{rid}: unknown right claim")
  if kind not in KINDS:e.append(f"{rid}: invalid relationship")
  key=(left,right,kind)
  if key in pairs:e.append(f"{rid}: duplicate relationship")
  pairs.add(key)
  if not isinstance(r.get("scope_comparison"),dict) or not r.get("scope_comparison"):e.append(f"{rid}: scope_comparison required")
  evidence=r.get("evidence")
  if not isinstance(evidence,list) or not evidence:e.append(f"{rid}: evidence required")
  else:
   for x in evidence:
    if not str(x.get("source_id","")).strip() or not str(x.get("citation_locator","")).strip():e.append(f"{rid}: evidence requires source_id and citation_locator")
  if kind=="supersedes" and r.get("review_state")!="approved":e.append(f"{rid}: supersedes requires approved review")
  if kind in {"contradicts","supersedes"} and r.get("review_state")=="approved":
   if left in known and not known[left].get("citation_verified"):e.append(f"{rid}: left claim citation is not verified")
   if right in known and not known[right].get("citation_verified"):e.append(f"{rid}: right claim citation is not verified")
 return e
def self_test():
 h1="a"*64;h2="b"*64;k={h1:{"citation_verified":True},h2:{"citation_verified":True}}
 good={"relationship_id":"r1","left_claim_sha256":h1,"right_claim_sha256":h2,"relationship":"contradicts","scope_comparison":{"population":"different cultivars"},"review_state":"approved","evidence":[{"source_id":"s","citation_locator":"p. 1"}]}
 assert not validate([good],k)
 assert validate([{**good,"relationship":"supersedes","review_state":"pending"}],k)
 assert validate([{**good,"right_claim_sha256":"c"*64}],k)
 assert validate([{**good,"scope_comparison":{}}],k)
 print("Grow Doc claim relationship self-test: PASS")
def main():
 a=argparse.ArgumentParser();a.add_argument("--input",type=pathlib.Path,default=ROOT/"dataset/reviewed/claim_relationships_v1.json");a.add_argument("--self-test",action="store_true");x=a.parse_args()
 if x.self_test:self_test();return 0
 d=load(x.input);e=validate(d.get("relationships",[]));print(json.dumps({"ok":not e,"relationship_count":len(d.get("relationships",[])),"errors":e},indent=2));return 0 if not e else 2
if __name__=="__main__":raise SystemExit(main())
