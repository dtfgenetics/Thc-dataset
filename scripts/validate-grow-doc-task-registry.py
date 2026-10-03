#!/usr/bin/env python3
"""Validate the machine-actionable Grow Doc task registry."""
from __future__ import annotations
import argparse,json,pathlib,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
LANES={"rag","diagnostic","sft","grounded_qa","eval","vision","compute","system"}
STATUSES={"active","blocked","done"}
REQUIRED=("id","lane","priority","status","title","evidence_gap","dependencies","allowed_paths","required_validators","definition_of_done")
def load(p): return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
def _covered(path,prefixes): return any(path==x or path.startswith(x) for x in prefixes)
def validate(doc,policy):
 e=[];tasks=doc.get("tasks")
 if doc.get("schema_version")!="grow-doc-task-registry-v2":e.append("unsupported task registry schema")
 if not isinstance(tasks,list) or not tasks:return e+["tasks must be a non-empty list"]
 ids=set()
 for i,t in enumerate(tasks,1):
  tid=str(t.get("id",""))
  for k in REQUIRED:
   if k not in t:e.append(f"row {i}: missing {k}")
  if not tid:e.append(f"row {i}: id required")
  elif tid in ids:e.append(f"duplicate task id: {tid}")
  ids.add(tid)
  lane=t.get("lane")
  if lane not in LANES:e.append(f"{tid}: invalid lane")
  if t.get("status") not in STATUSES:e.append(f"{tid}: invalid status")
  for key in ("evidence_gap","title","priority"):
   if not str(t.get(key,"")).strip():e.append(f"{tid}: {key} required")
  for key in ("dependencies","allowed_paths","required_validators","definition_of_done"):
   if not isinstance(t.get(key),list):e.append(f"{tid}: {key} must be a list")
  if not t.get("allowed_paths"):e.append(f"{tid}: allowed_paths required")
  if not t.get("required_validators"):e.append(f"{tid}: required_validators required")
  if not t.get("definition_of_done"):e.append(f"{tid}: definition_of_done required")
  if t.get("status")=="blocked" and not str(t.get("blocker","")).strip():e.append(f"{tid}: blocked task requires blocker")
  if lane in policy.get("lanes",{}):
   allowed=policy["lanes"][lane].get("allowed_prefixes",[])
   for p in t.get("allowed_paths") or []:
    if not _covered(str(p),allowed):e.append(f"{tid}: path outside {lane} routing policy: {p}")
 for t in tasks:
  tid=t.get("id")
  for dep in t.get("dependencies") or []:
   if dep==tid:e.append(f"{tid}: task cannot depend on itself")
   elif dep not in ids:e.append(f"{tid}: unknown dependency {dep}")
 return e
def self_test():
 policy={"lanes":{"rag":{"allowed_prefixes":["dataset/reviewed/"]}}}
 good={"schema_version":"grow-doc-task-registry-v2","tasks":[{"id":"GD-RAG-001","lane":"rag","priority":"P0","status":"active","title":"x","evidence_gap":"y","dependencies":[],"allowed_paths":["dataset/reviewed/"],"required_validators":["v"],"definition_of_done":["d"]}]}
 assert not validate(good,policy)
 bad=json.loads(json.dumps(good));bad["tasks"][0]["allowed_paths"]=["model_tuning/eval/"];assert validate(bad,policy)
 bad=json.loads(json.dumps(good));bad["tasks"][0]["status"]="blocked";assert validate(bad,policy)
 print("Grow Doc task registry self-test: PASS")
def main():
 a=argparse.ArgumentParser();a.add_argument("--registry",type=pathlib.Path,default=ROOT/"contributions/tasks.json");a.add_argument("--policy",type=pathlib.Path,default=ROOT/"contributions/routing-policy.json");a.add_argument("--self-test",action="store_true");x=a.parse_args()
 if x.self_test:self_test();return 0
 e=validate(load(x.registry),load(x.policy));print(json.dumps({"ok":not e,"errors":e},indent=2));return 0 if not e else 2
if __name__=="__main__":raise SystemExit(main())
