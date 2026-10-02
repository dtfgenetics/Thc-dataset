#!/usr/bin/env python3
"""Normalize scientific claims and derive RAG eligibility from explicit review gates."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
SCHEMA="grow-doc-reviewed-claim-v1"
APPROVED={"approved"}
def s(v):return str(v).strip() if v is not None else ""
def normalize(r:dict,known:set[str])->dict:
 source=s(r.get("source_id"));claim=s(r.get("claim"));locator=s(r.get("citation_locator"))
 if not source or source not in known:raise ValueError("claim source_id is missing or not admitted")
 if not claim:raise ValueError("claim text required")
 if not locator:raise ValueError("citation_locator required")
 scope=r.get("scope")
 if not isinstance(scope,dict) or not scope:raise ValueError("non-empty claim scope required")
 review=s(r.get("review_state")) or "pending"
 limitations=r.get("limitations") or []
 if not isinstance(limitations,list):raise ValueError("limitations must be a list")
 rights=s(r.get("rights_state")) or "review_required"
 rag=(review in APPROVED and rights in {"reviewed","government_source_reviewed"} and bool(r.get("citation_verified",False)))
 out={"schema_version":SCHEMA,"source_id":source,"claim":claim,"citation_locator":locator,"scope":scope,
      "limitations":limitations,"review_state":review,"rights_state":rights,"citation_verified":bool(r.get("citation_verified",False)),
      "rag_eligible":rag,"weight_training_eligible":False}
 out["claim_sha256"]=hashlib.sha256(json.dumps(out,sort_keys=True,separators=(",",":")).encode()).hexdigest();return out
def known_sources(p:Path)->set[str]:
 d=json.loads(p.read_text());return {s(x.get("source_id")) for x in d.get("sources",[]) if s(x.get("source_id"))}
def self_test(tmp:Path):
 p=tmp/"c.json";p.write_text(json.dumps({"sources":[{"source_id":"s"}]}));k=known_sources(p)
 base={"source_id":"s","claim":"Measured response differed by treatment.","citation_locator":"p. 10","scope":{"population":"study cohort"}}
 assert normalize(base,k)["rag_eligible"] is False
 good={**base,"review_state":"approved","rights_state":"reviewed","citation_verified":True}
 assert normalize(good,k)["rag_eligible"] is True and normalize(good,k)["weight_training_eligible"] is False
 for bad in ({**base,"source_id":"unknown"},{**base,"citation_locator":""},{**base,"scope":{}}):
  try:normalize(bad,k);raise AssertionError("invalid claim accepted")
  except ValueError:pass
 print("reviewed claim contract self-test: PASS")
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--catalog",type=Path);ap.add_argument("--input",type=Path);ap.add_argument("--output",type=Path);ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
 if a.self_test:
  import tempfile
  with tempfile.TemporaryDirectory() as d:self_test(Path(d))
  return 0
 if not a.catalog or not a.input or not a.output:ap.error("--catalog --input --output required")
 k=known_sources(a.catalog);d=json.loads(a.input.read_text());rows=d if isinstance(d,list) else d.get("claims",[])
 out=[normalize(x,k) for x in rows];out.sort(key=lambda x:(x["source_id"],x["claim_sha256"]))
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({"schema_version":SCHEMA,"claims":out},indent=2,sort_keys=True)+"\n");return 0
if __name__=="__main__":raise SystemExit(main())
