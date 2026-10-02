#!/usr/bin/env python3
"""Fail-closed status and contribution-receipt validator for Grow Doc."""
from __future__ import annotations
import argparse,hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
LANES={"rag","diagnostic","sft","grounded_qa","eval","vision","compute","system"}
def load(p): return json.loads((ROOT/p).read_text(encoding="utf-8"))
def digest(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def status():
 ref=load("images/reference/manifest.json"); crops=load("images/reference/crops-manifest.json")
 ready=load("data/model-training-readiness.json"); split=load("data/splits/manifest.json"); tasks=load("contributions/tasks.json")["tasks"]
 o,c=ref["recordCount"],crops["recordCount"]; total=o+c; errors=[]
 checks=[("readiness originals",ready["visionLayer"]["referenceOriginals"],o),("readiness crops",ready["visionLayer"]["referenceCrops"],c),("readiness total",ready["visionLayer"]["totalReferenceImages"],total),("split originals",split["knowledgeLayerSnapshot"]["referenceOriginals"],o),("split crops",split["knowledgeLayerSnapshot"]["referenceCrops"],c)]
 for name,actual,wanted in checks:
  if actual!=wanted: errors.append(f"{name}: {actual} != {wanted}")
 eligible=int(ready["visionLayer"]["trainingEligibleSamples"])
 if eligible==0 and (ready["readyForSupervisedCannabisDiagnosisTraining"] or split["ready"]): errors.append("vision training must remain blocked with zero eligible samples")
 return {"schema_version":"grow-doc-contribution-status-v1","ok":not errors,"reference_media":{"originals":o,"crops":c,"total":total,"training_eligible":eligible},"supervised_vision_ready":bool(ready["readyForSupervisedCannabisDiagnosisTraining"]),"tasks":{"total":len(tasks),"active":sum(x.get("status")=="active" for x in tasks),"blocked":sum(x.get("status")=="blocked" for x in tasks)},"canonical_hashes":{"reference_manifest":digest("images/reference/manifest.json"),"crop_manifest":digest("images/reference/crops-manifest.json"),"model_readiness":digest("data/model-training-readiness.json"),"split_manifest":digest("data/splits/manifest.json")},"errors":errors}
def route_manifest(p):
 m=json.loads(p.read_text(encoding="utf-8")); policy=load("contributions/routing-policy.json"); tasks={x["id"]:x for x in load("contributions/tasks.json")["tasks"]};e=[]
 lane=m.get("lane");tid=m.get("task_id");paths=m.get("changed_paths",[])
 if lane not in policy["lanes"]:e.append("unknown lane");return {"ok":False,"errors":e}
 if tid not in tasks:e.append("unknown task_id")
 elif tasks[tid].get("lane")!=lane:e.append(f"task lane {tasks[tid].get('lane')} != manifest lane {lane}")
 rule=policy["lanes"][lane]
 for path in paths:
  if any(path.startswith(x) for x in rule.get("forbidden_prefixes",[])):e.append(f"forbidden path for {lane}: {path}")
  if not any(path==x or path.startswith(x) for x in rule.get("allowed_prefixes",[])):e.append(f"path outside {lane} routing policy: {path}")
 receipt={"schema_version":"grow-doc-contribution-receipt-v1","contribution_id":m.get("contribution_id",""),"task_id":tid,"lane":lane,"base_commit":m.get("base_commit",""),"branch":m.get("branch",""),"changed_paths":paths,"source_ids":m.get("source_ids",[]),"validation":{"required":rule.get("required_validators",[]),"completed":[]} }
 if rule.get("training_eligible") is False:receipt["training_eligible"]=False;receipt["weight_training_eligible"]=False
 return {"ok":not e,"errors":e,"required_validators":rule.get("required_validators",[]),"receipt":receipt}
def validate_claims():
 tasks={x["id"]:x for x in load("contributions/tasks.json")["tasks"]}
 rows=load("contributions/claims.json").get("claims",[]);e=[];seen={}
 for r in rows:
  tid=str(r.get("task_id",""));sid=str(r.get("session_id",""));branch=str(r.get("branch",""))
  if tid not in tasks:e.append(f"unknown claimed task: {tid}");continue
  if tasks[tid].get("status")=="blocked":e.append(f"blocked task cannot be claimed: {tid}")
  if not sid:e.append(f"{tid}: session_id required")
  if not branch.startswith("work/grow-doc/"):e.append(f"{tid}: invalid branch")
  if tid in seen:e.append(f"task collision: {tid} claimed by {seen[tid]} and {sid}")
  else:seen[tid]=sid
 return e
def validate_receipt(p):
 r=json.loads(p.read_text(encoding="utf-8")); e=[]
 for k in ("schema_version","contribution_id","task_id","lane","base_commit","branch","changed_paths","source_ids","validation"):
  if k not in r:e.append(f"missing {k}")
 if r.get("schema_version")!="grow-doc-contribution-receipt-v1":e.append("unsupported schema_version")
 if r.get("lane") not in LANES:e.append("invalid lane")
 if r.get("lane")=="rag" and r.get("weight_training_eligible") is not False:e.append("RAG factual contribution must not be weight-training eligible")
 if r.get("lane")=="eval" and r.get("training_eligible") is not False:e.append("evaluation contribution must not be training eligible")
 if r.get("lane")=="vision" and r.get("training_eligible") is True and not r.get("human_reviewed"):e.append("vision training eligibility requires human review")
 return e
def self_test():
 s=status();assert s["ok"],s["errors"];assert not validate_claims()
 import tempfile
 good={"schema_version":"grow-doc-contribution-receipt-v1","contribution_id":"x","task_id":"GD-RAG-001","lane":"rag","base_commit":"abc","branch":"work/grow-doc/x/y","changed_paths":[],"source_ids":[],"validation":{},"weight_training_eligible":False}
 with tempfile.TemporaryDirectory() as d:
  p=pathlib.Path(d)/"r.json";p.write_text(json.dumps(good));assert not validate_receipt(p)
  good["weight_training_eligible"]=True;p.write_text(json.dumps(good));assert validate_receipt(p)
 bad={"contribution_id":"x","task_id":"GD-RAG-001","lane":"rag","base_commit":"abcdef1","branch":"work/grow-doc/x/y","changed_paths":["model_tuning/eval/heldout_v3.jsonl"],"source_ids":[]}
 with tempfile.TemporaryDirectory() as d:
  p=pathlib.Path(d)/"m.json";p.write_text(json.dumps(bad));assert not route_manifest(p)["ok"]
 print("Grow Doc contribution controller self-test: PASS")
def main():
 a=argparse.ArgumentParser();a.add_argument("--validate-receipt",type=pathlib.Path);a.add_argument("--validate-claims",action="store_true");a.add_argument("--route-manifest",type=pathlib.Path);a.add_argument("--self-test",action="store_true");x=a.parse_args()
 if x.self_test:self_test();return 0
 if x.route_manifest:
  r=route_manifest(x.route_manifest);print(json.dumps(r,indent=2,sort_keys=True));return 0 if r["ok"] else 2
 if x.validate_claims:
  e=validate_claims();print(json.dumps({"ok":not e,"errors":e},indent=2));return 0 if not e else 2
 if x.validate_receipt:
  e=validate_receipt(x.validate_receipt);print(json.dumps({"ok":not e,"errors":e},indent=2));return 0 if not e else 2
 s=status();print(json.dumps(s,indent=2,sort_keys=True));return 0 if s["ok"] else 2
if __name__=="__main__":raise SystemExit(main())
