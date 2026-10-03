#!/usr/bin/env python3
"""Build RAG-first supplied-claim QA candidates from approved reviewed claims."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,pathlib,re,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CLAIMS=ROOT/"dataset/reviewed/cornell_reviewed_claims_v1.json"
DEFAULT_CATALOG=ROOT/"dataset/generated/tool_data/source_catalog_v1.json"
DEFAULT_EVAL=ROOT/"model_tuning/eval/heldout_v3.jsonl"
DEFAULT_OUT=ROOT/"model_tuning/grounded_qa/reviewed_claims_v1.jsonl"
def load_module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
GROUND=load_module(ROOT/"scripts/enforce-supplied-claim-grounding.py","grow_doc_supplied_claims")
def sha(s):return hashlib.sha256(s.encode("utf-8")).hexdigest()
def canon(raw):
 v=str(raw or "").strip()
 v=re.sub(r"(?i)^doi:\s*","",v);v=re.sub(r"(?i)^https?://(?:dx\.)?doi\.org/","",v)
 if re.match(r"(?i)^10\.\d{4,9}/\S+$",v):return "doi:"+v.lower()
 if re.match(r"(?i)^https?://",v):return "url:"+v
 return v.lower()
def heldout(path):
 out=set()
 if not path.exists():return out
 for line in path.read_text(encoding="utf-8").splitlines():
  if not line.strip():continue
  for x in json.loads(line).get("must_cite") or []:
   c=canon(x)
   if c:out.add(c)
 return out
def identities(source):
 vals={canon(source.get("source_id"))}
 p=source.get("persistent_ids") or {}
 if p.get("doi"):vals.add(canon(p["doi"]))
 if source.get("canonical_url"):vals.add(canon(source["canonical_url"]))
 return {x for x in vals if x}
def build(claims_doc,catalog_doc,eval_path):
 sources={x["source_id"]:x for x in catalog_doc.get("sources",[]) if x.get("source_id")}
 reserved=heldout(eval_path);rows=[];skipped={"not_rag_eligible":0,"heldout_source":0}
 for c in claims_doc.get("claims",[]):
  if c.get("rag_eligible") is not True or c.get("weight_training_eligible") is not False:
   skipped["not_rag_eligible"]+=1;continue
  sid=c.get("source_id");src=sources.get(sid)
  if not src:raise ValueError(f"unknown reviewed source: {sid}")
  if identities(src)&reserved:skipped["heldout_source"]+=1;continue
  claim=str(c.get("claim","")).strip()
  if not claim:raise ValueError("reviewed claim text required")
  text_hash=sha(claim);pairs=[(sid,claim)]
  row={"id":"gqa-reviewed-"+c["claim_sha256"][:16],"task":"grounded_qa","profile_id":"reviewed-claim:"+sid,
       "source_ids":[sid],"reviewed_claim_sha256":c["claim_sha256"],"citation_locator":c["citation_locator"],
       "scope":c["scope"],"limitations":c.get("limitations") or [],"rag_first":True,"training_eligible":False,
       "grounding_mode":"supplied_claims_only_v1","evidence_claims":[{"source_id":sid,"claim":claim,"claim_sha256":text_hash}],
       "evidence_claim_sha256s":[text_hash],"messages":[
        {"role":"system","content":"Answer only from the supplied evidence. Preserve scope and uncertainty; do not add uncited facts."},
        {"role":"user","content":GROUND.task_prompt("grounded_qa",GROUND.canonical_evidence(pairs))},
        {"role":"assistant","content":GROUND.assistant_target("grounded_qa",pairs)}]}
  errors=GROUND.validate_row(row)
  if errors:raise ValueError("; ".join(errors))
  rows.append(row)
 rows.sort(key=lambda x:x["id"])
 return rows,{"examples":len(rows),"heldout_source_ids":len(reserved),"skipped":skipped,"policy":"reviewed RAG claims become supplied-evidence behavior candidates; facts remain in prompt; training admission remains separate"}
def render(rows):return "".join(json.dumps(x,ensure_ascii=False,separators=(",",":"))+"\n" for x in rows)
def self_test():
 claims={"claims":[{"claim_sha256":"a"*64,"source_id":"s","claim":"Scoped result.","citation_locator":"p.1","scope":{"study":"x"},"limitations":[],"rag_eligible":True,"weight_training_eligible":False}]}
 catalog={"sources":[{"source_id":"s","persistent_ids":{"doi":"10.x/train"}}]}
 with tempfile.TemporaryDirectory() as td:
  p=pathlib.Path(td)/"e.jsonl";p.write_text('{"must_cite":["doi:10.x/other"]}\n')
  rows,stats=build(claims,catalog,p);assert len(rows)==1 and rows[0]["training_eligible"] is False;assert not GROUND.validate_row(rows[0])
  p.write_text('{"must_cite":["doi:10.x/train"]}\n');rows,stats=build(claims,catalog,p);assert not rows and stats["skipped"]["heldout_source"]==1
 print("reviewed-claim grounded QA self-test: PASS")
def main():
 a=argparse.ArgumentParser();a.add_argument("--claims",type=pathlib.Path,default=DEFAULT_CLAIMS);a.add_argument("--catalog",type=pathlib.Path,default=DEFAULT_CATALOG);a.add_argument("--eval",type=pathlib.Path,default=DEFAULT_EVAL);a.add_argument("--out",type=pathlib.Path,default=DEFAULT_OUT);a.add_argument("--check-only",action="store_true");a.add_argument("--self-test",action="store_true");x=a.parse_args()
 if x.self_test:self_test();return 0
 rows,stats=build(json.loads(x.claims.read_text()),json.loads(x.catalog.read_text()),x.eval);raw=render(rows)
 if x.check_only:
  if not x.out.exists() or x.out.read_text(encoding="utf-8")!=raw:print(json.dumps({"ok":False,"reason":"committed artifact differs from deterministic builder","stats":stats},sort_keys=True));return 2
 else:x.out.parent.mkdir(parents=True,exist_ok=True);x.out.write_text(raw,encoding="utf-8")
 print(json.dumps({"ok":True,"stats":stats},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
