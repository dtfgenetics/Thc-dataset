#!/usr/bin/env python3
"""Fail-closed status, routing, ownership, and contribution-receipt controls for Grow Doc."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
LANES={"rag","diagnostic","sft","grounded_qa","eval","vision","compute","system"}
RECEIPT_SCHEMA="grow-doc-contribution-receipt-v1"

def load(p): return json.loads((ROOT/p).read_text(encoding="utf-8"))
def digest(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def task_map(): return {x["id"]:x for x in load("contributions/tasks.json")["tasks"]}
def stable_union(*groups):
 out=[]
 for group in groups:
  for value in group or []:
   if value not in out: out.append(value)
 return out
def path_allowed(path,prefixes): return any(path==x or path.startswith(x) for x in prefixes or [])

def status():
 ref=load("images/reference/manifest.json");crops=load("images/reference/crops-manifest.json")
 ready=load("data/model-training-readiness.json");split=load("data/splits/manifest.json");tasks=list(task_map().values())
 o,c=ref["recordCount"],crops["recordCount"];total=o+c;errors=[]
 checks=[("readiness originals",ready["visionLayer"]["referenceOriginals"],o),("readiness crops",ready["visionLayer"]["referenceCrops"],c),("readiness total",ready["visionLayer"]["totalReferenceImages"],total),("split originals",split["knowledgeLayerSnapshot"]["referenceOriginals"],o),("split crops",split["knowledgeLayerSnapshot"]["referenceCrops"],c)]
 for name,actual,wanted in checks:
  if actual!=wanted: errors.append(f"{name}: {actual} != {wanted}")
 eligible=int(ready["visionLayer"]["trainingEligibleSamples"])
 if eligible==0 and (ready["readyForSupervisedCannabisDiagnosisTraining"] or split["ready"]):errors.append("vision training must remain blocked with zero eligible samples")
 return {"schema_version":"grow-doc-contribution-status-v1","ok":not errors,"reference_media":{"originals":o,"crops":c,"total":total,"training_eligible":eligible},"supervised_vision_ready":bool(ready["readyForSupervisedCannabisDiagnosisTraining"]),"tasks":{"total":len(tasks),"active":sum(x.get("status")=="active" for x in tasks),"blocked":sum(x.get("status")=="blocked" for x in tasks)},"canonical_hashes":{"reference_manifest":digest("images/reference/manifest.json"),"crop_manifest":digest("images/reference/crops-manifest.json"),"model_readiness":digest("data/model-training-readiness.json"),"split_manifest":digest("data/splits/manifest.json")},"errors":errors}

def route_contract(lane,tid):
 policy=load("contributions/routing-policy.json");tasks=task_map();e=[]
 if lane not in policy["lanes"]:return None,None,["unknown lane"]
 task=tasks.get(tid)
 if task is None:return None,None,["unknown task_id"]
 if task.get("lane")!=lane:e.append(f"task lane {task.get('lane')} != manifest lane {lane}")
 if task.get("status")!="active":e.append(f"task is not active: {tid}")
 rule=policy["lanes"][lane]
 required=stable_union(rule.get("required_validators"),task.get("required_validators"))
 return task,rule,e+[f"task dependency not complete: {dep}" for dep in task.get("dependencies",[]) if tasks.get(dep,{}).get("status")=="blocked"]

def validate_paths(lane,task,rule,paths):
 e=[]
 if not isinstance(paths,list):return ["changed_paths must be a list"]
 if len(set(paths))!=len(paths):e.append("changed_paths must not contain duplicates")
 for path in paths:
  if not isinstance(path,str) or not path.strip():e.append("changed_paths must contain non-empty strings");continue
  if any(path.startswith(x) for x in rule.get("forbidden_prefixes",[])):e.append(f"forbidden path for {lane}: {path}")
  if not path_allowed(path,rule.get("allowed_prefixes",[])):e.append(f"path outside {lane} routing policy: {path}")
  if not path_allowed(path,task.get("allowed_paths",[])):e.append(f"path outside task ownership: {path}")
 return e

def route_manifest(p):
 m=json.loads(p.read_text(encoding="utf-8"));lane=m.get("lane");tid=m.get("task_id");paths=m.get("changed_paths",[])
 task,rule,e=route_contract(lane,tid)
 if task is None or rule is None:return {"ok":False,"errors":e}
 e.extend(validate_paths(lane,task,rule,paths))
 required=stable_union(rule.get("required_validators"),task.get("required_validators"))
 receipt={"schema_version":RECEIPT_SCHEMA,"contribution_id":m.get("contribution_id",""),"task_id":tid,"lane":lane,"base_commit":m.get("base_commit",""),"branch":m.get("branch",""),"changed_paths":paths,"source_ids":m.get("source_ids",[]),"validation":{"required":required,"completed":[]}}
 if rule.get("training_eligible") is False:receipt["training_eligible"]=False;receipt["weight_training_eligible"]=False
 if lane=="rag":receipt["weight_training_eligible"]=False
 return {"ok":not e,"errors":e,"required_validators":required,"receipt":receipt}

def validate_claims():
 tasks=task_map();rows=load("contributions/claims.json").get("claims",[]);e=[];seen={}
 for r in rows:
  tid=str(r.get("task_id",""));sid=str(r.get("session_id",""));branch=str(r.get("branch",""))
  if tid not in tasks:e.append(f"unknown claimed task: {tid}");continue
  if tasks[tid].get("status")!="active":e.append(f"non-active task cannot be claimed: {tid}")
  if not sid:e.append(f"{tid}: session_id required")
  if not branch.startswith("work/grow-doc/"):e.append(f"{tid}: invalid branch")
  if tid in seen:e.append(f"task collision: {tid} claimed by {seen[tid]} and {sid}")
  else:seen[tid]=sid
 return e

def validate_receipt_data(r):
 e=[]
 required_fields=("schema_version","contribution_id","task_id","lane","base_commit","branch","changed_paths","source_ids","validation")
 for k in required_fields:
  if k not in r:e.append(f"missing {k}")
 if r.get("schema_version")!=RECEIPT_SCHEMA:e.append("unsupported schema_version")
 lane=r.get("lane");tid=r.get("task_id")
 if lane not in LANES:e.append("invalid lane");return e
 if not isinstance(r.get("contribution_id"),str) or not r.get("contribution_id","").strip():e.append("contribution_id required")
 base=str(r.get("base_commit",""))
 if len(base)<7 or len(base)>64 or any(c not in "0123456789abcdef" for c in base):e.append("base_commit must be lowercase hex with length 7-64")
 if not isinstance(r.get("branch"),str) or not r.get("branch","").startswith("work/grow-doc/"):e.append("branch must start with work/grow-doc/")
 source_ids=r.get("source_ids")
 if not isinstance(source_ids,list) or any(not isinstance(x,str) or not x.strip() for x in source_ids):e.append("source_ids must be a list of non-empty strings")
 elif len(set(source_ids))!=len(source_ids):e.append("source_ids must not contain duplicates")
 task,rule,contract_errors=route_contract(lane,tid);e.extend(contract_errors)
 if task is not None and rule is not None:e.extend(validate_paths(lane,task,rule,r.get("changed_paths")))
 validation=r.get("validation")
 if not isinstance(validation,dict):e.append("validation must be an object")
 else:
  if set(validation)!={"required","completed"}:e.append("validation must contain only required and completed")
  req=validation.get("required");done=validation.get("completed")
  if not isinstance(req,list) or any(not isinstance(x,str) or not x for x in req):e.append("validation.required must be a list of strings")
  if not isinstance(done,list) or any(not isinstance(x,str) or not x for x in done):e.append("validation.completed must be a list of strings")
  if isinstance(req,list) and isinstance(done,list) and task is not None and rule is not None:
   expected=stable_union(rule.get("required_validators"),task.get("required_validators"))
   if req!=expected:e.append(f"validation.required does not match routing/task contract: expected {expected}")
   missing=[x for x in expected if x not in done]
   if missing:e.append(f"required validators not completed: {missing}")
   extras=[x for x in done if x not in req]
   if extras:e.append(f"completed validators not declared required: {extras}")
 if lane=="rag" and r.get("weight_training_eligible") is not False:e.append("RAG factual contribution must not be weight-training eligible")
 if lane=="eval" and r.get("training_eligible") is not False:e.append("evaluation contribution must not be training eligible")
 if lane=="vision" and r.get("training_eligible") is True and not r.get("human_reviewed"):e.append("vision training eligibility requires human review")
 return e

def validate_receipt(p):return validate_receipt_data(json.loads(p.read_text(encoding="utf-8")))

def validate_receipts_dir(path):
 errors=[]
 for receipt in sorted(path.glob("*.json")):
  try:e=validate_receipt(receipt)
  except (OSError,json.JSONDecodeError) as exc:e=[f"invalid receipt JSON: {exc}"]
  errors.extend(f"{receipt.name}: {message}" for message in e)
 return errors

def self_test():
 s=status();assert s["ok"],s["errors"];assert not validate_claims()
 task,rule,e=route_contract("rag","GD-RAG-001");assert not e
 required=stable_union(rule.get("required_validators"),task.get("required_validators"))
 good={"schema_version":RECEIPT_SCHEMA,"contribution_id":"x","task_id":"GD-RAG-001","lane":"rag","base_commit":"abcdef1","branch":"work/grow-doc/x/y","changed_paths":["dataset/reviewed/test.json"],"source_ids":["doi:10.test/example"],"validation":{"required":required,"completed":required},"weight_training_eligible":False}
 assert not validate_receipt_data(good)
 bad=json.loads(json.dumps(good));bad["validation"]["completed"]=bad["validation"]["completed"][:-1];assert any("not completed" in x for x in validate_receipt_data(bad))
 bad=json.loads(json.dumps(good));bad["changed_paths"]=["model_tuning/eval/heldout_v3.jsonl"];assert any("forbidden path" in x or "outside" in x for x in validate_receipt_data(bad))
 bad=json.loads(json.dumps(good));bad["weight_training_eligible"]=True;assert any("must not be weight-training eligible" in x for x in validate_receipt_data(bad))
 manifest={"contribution_id":"x","task_id":"GD-RAG-001","lane":"rag","base_commit":"abcdef1","branch":"work/grow-doc/x/y","changed_paths":["dataset/reviewed/test.json"],"source_ids":["doi:10.test/example"]}
 with tempfile.TemporaryDirectory() as d:
  p=pathlib.Path(d)/"m.json";p.write_text(json.dumps(manifest));r=route_manifest(p);assert r["ok"];assert r["required_validators"]==required
 print("Grow Doc contribution controller self-test: PASS")

def main():
a=argparse.ArgumentParser();a.add_argument("--validate-receipt",type=pathlib.Path);a.add_argument("--validate-receipts-dir",type=pathlib.Path);a.add_argument("--validate-claims",action="store_true");a.add_argument("--route-manifest",type=pathlib.Path);a.add_argument("--self-test",action="store_true");x=a.parse_args()
 if x.self_test:self_test();return 0
 if x.route_manifest:
  r=route_manifest(x.route_manifest);print(json.dumps(r,indent=2,sort_keys=True));return 0 if r["ok"] else 2
 if x.validate_claims:
  e=validate_claims();print(json.dumps({"ok":not e,"errors":e},indent=2));return 0 if not e else 2
 if x.validate_receipt:
  e=validate_receipt(x.validate_receipt);print(json.dumps({"ok":not e,"errors":e},indent=2));return 0 if not e else 2
 if x.validate_receipts_dir:
  e=validate_receipts_dir(x.validate_receipts_dir);print(json.dumps({"ok":not e,"errors":e},indent=2));return 0 if not e else 2
 s=status();print(json.dumps(s,indent=2,sort_keys=True));return 0 if s["ok"] else 2
if __name__=="__main__":raise SystemExit(main())
