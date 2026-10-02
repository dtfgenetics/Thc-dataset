#!/usr/bin/env python3
"""Classify candidate scientific claims before reviewed-claim/RAG publication."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(p):return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
def admitted_ids():
 ids=set()
 for p in (ROOT/"dataset/registry").glob("sources-*.json"):
  d=load(p)
  for x in d.get("sources",[]): 
   if x.get("source_id"):ids.add(str(x["source_id"]).strip())
 return ids
def existing_claims():
 seen=set()
 for p in (ROOT/"dataset/reviewed").glob("*.json"):
  for x in load(p).get("claims",[]):
   if x.get("claim_sha256"):seen.add(x["claim_sha256"])
   seen.add("text:"+str(x.get("claim","")).strip().lower())
 return seen
def claim_hash(r):
 core={k:r.get(k) for k in ("source_id","claim","citation_locator","scope","limitations","review_state","rights_state","citation_verified")}
 return hashlib.sha256(json.dumps(core,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def classify(r,known,seen):
 errors=[];review=[]
 sid=str(r.get("source_id","")).strip();claim=str(r.get("claim","")).strip();loc=str(r.get("citation_locator","")).strip()
 if not sid or sid not in known:errors.append("source_id is not admitted in canonical source registry")
 if not claim:errors.append("claim text required")
 if not loc:errors.append("citation_locator required")
 if not isinstance(r.get("scope"),dict) or not r.get("scope"):errors.append("non-empty scope required")
 if not isinstance(r.get("limitations",[]),list):errors.append("limitations must be a list")
 if "text:"+claim.lower() in seen:errors.append("duplicate reviewed claim text")
 tier=str(r.get("evidence_tier","")).strip()
 if tier not in {"scholarly_doi","institutional_web","general_web"}:review.append("evidence tier requires review")
 if tier=="general_web":review.append("general web evidence is retrieval/support only; independent stronger evidence required for scientific ground truth")
 if r.get("review_state")!="approved":review.append("claim review approval required")
 if r.get("rights_state") not in {"reviewed","government_source_reviewed"}:review.append("rights review required")
 if r.get("citation_verified") is not True:review.append("citation verification required")
 state="quarantine" if errors else ("review_required" if review else "rag_admissible")
 return {"state":state,"source_id":sid,"claim_sha256":claim_hash(r),"errors":errors,"review_requirements":review,"weight_training_eligible":False,"rag_eligible":state=="rag_admissible"}
def run(rows):
 known=admitted_ids();seen=existing_claims();out=[]
 for r in rows:
  x=classify(r,known,seen);out.append(x);seen.add("text:"+str(r.get("claim","")).strip().lower())
 return {"schema_version":"grow-doc-source-intake-v1","summary":{s:sum(x["state"]==s for x in out) for s in ("rag_admissible","review_required","quarantine")},"results":out}
def self_test():
 known={"s"};seen=set();base={"source_id":"s","claim":"Measured response differed by treatment.","citation_locator":"p. 1","scope":{"population":"study"},"limitations":[],"evidence_tier":"scholarly_doi"}
 assert classify(base,known,seen)["state"]=="review_required"
 good={**base,"review_state":"approved","rights_state":"reviewed","citation_verified":True}
 assert classify(good,known,seen)["state"]=="rag_admissible"
 assert classify({**good,"source_id":"x"},known,seen)["state"]=="quarantine"
 assert classify({**good,"evidence_tier":"general_web"},known,seen)["state"]=="review_required"
 print("Grow Doc source intake self-test: PASS")
def main():
 a=argparse.ArgumentParser();a.add_argument("--input",type=pathlib.Path);a.add_argument("--output",type=pathlib.Path);a.add_argument("--self-test",action="store_true");x=a.parse_args()
 if x.self_test:self_test();return 0
 if not x.input:a.error("--input required")
 d=load(x.input);rows=d if isinstance(d,list) else d.get("claims",[]);result=run(rows);text=json.dumps(result,indent=2,sort_keys=True)+"\n"
 if x.output:x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(text,encoding="utf-8")
 else:sys.stdout.write(text)
 return 2 if result["summary"]["quarantine"] else 0
if __name__=="__main__":raise SystemExit(main())
