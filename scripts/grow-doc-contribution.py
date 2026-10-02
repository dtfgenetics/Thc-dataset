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
 s=status();assert s["ok"],s["errors"]
 import tempfile
 good={"schema_version":"grow-doc-contribution-receipt-v1","contribution_id":"x","task_id":"GD-RAG-001","lane":"rag","base_commit":"abc","branch":"work/grow-doc/x/y","changed_paths":[],"source_ids":[],"validation":{},"weight_training_eligible":False}
 with tempfile.TemporaryDirectory() as d:
  p=pathlib.Path(d)/"r.json";p.write_text(json.dumps(good));assert not validate_receipt(p)
  good["weight_training_eligible"]=True;p.write_text(json.dumps(good));assert validate_receipt(p)
 print("Grow Doc contribution controller self-test: PASS")
def main():
 a=argparse.ArgumentParser();a.add_argument("--validate-receipt",type=pathlib.Path);a.add_argument("--self-test",action="store_true");x=a.parse_args()
 if x.self_test:self_test();return 0
 if x.validate_receipt:
  e=validate_receipt(x.validate_receipt);print(json.dumps({"ok":not e,"errors":e},indent=2));return 0 if not e else 2
 s=status();print(json.dumps(s,indent=2,sort_keys=True));return 0 if s["ok"] else 2
if __name__=="__main__":raise SystemExit(main())
