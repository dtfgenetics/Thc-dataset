#!/usr/bin/env python3
"""Validate the durable Grow Doc experiment registry."""
from __future__ import annotations
import argparse,json,pathlib,re,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT=ROOT/"model_tuning/experiments/registry_v1.json"
TASKS=ROOT/"contributions/tasks.json"
CANDIDATES=ROOT/"model_tuning/config/base_model_candidates_v1.json"
REQUIRED_SLICES={"factuality","diagnostic","hallucination","citation_accuracy","science","education","grounded_qa","regression"}
STATUSES={"planned","blocked","running","succeeded","failed","aborted","reviewed"}
KINDS={"base_vs_rag","qlora","adapter_eval","adapter_combination"}
SHA40=re.compile(r"^[0-9a-f]{40}$")
SHA256=re.compile(r"^[0-9a-f]{64}$")

def fail(msg):raise ValueError(msg)
def load(path):return json.loads(path.read_text(encoding="utf-8"))
def validate_doc(data,tasks,candidates):
 if data.get("schema_version")!="grow-doc-experiment-registry-v1":fail("unsupported experiment registry schema")
 policy=data.get("policy") or {}
 for key in ("append_only_intent","retain_failed_and_aborted_runs","registry_never_authorizes_promotion"):
  if policy.get(key) is not True:fail(f"policy {key} must be true")
 if set(policy.get("required_protected_slices") or [])!=REQUIRED_SLICES:fail("policy required_protected_slices must match locked slices")
 task_map={x["id"]:x for x in tasks.get("tasks",[])}
 candidate_map={x["id"]:x for x in candidates.get("candidates",[])}
 rows=data.get("experiments")
 if not isinstance(rows,list) or not rows:fail("experiment registry must contain at least one experiment")
 seen=set()
 for row in rows:
  eid=row.get("experiment_id")
  if not isinstance(eid,str) or not eid.strip() or eid in seen:fail(f"invalid or duplicate experiment_id: {eid!r}")
  seen.add(eid)
  status=row.get("status");kind=row.get("kind")
  if status not in STATUSES:fail(f"{eid}: invalid status")
  if kind not in KINDS:fail(f"{eid}: invalid kind")
  tid=row.get("task_id")
  if tid not in task_map:fail(f"{eid}: unknown task_id {tid}")
  if task_map[tid].get("lane")!="compute":fail(f"{eid}: experiment task must use compute lane")
  ids=row.get("candidate_ids")
  if not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)):fail(f"{eid}: candidate_ids must be unique non-empty list")
  for cid in ids:
   if cid not in candidate_map:fail(f"{eid}: unknown candidate_id {cid}")
  if row.get("benchmark_path")!="model_tuning/eval/heldout_v3.jsonl":fail(f"{eid}: benchmark must remain heldout_v3")
  if set(row.get("required_slices") or [])!=REQUIRED_SLICES:fail(f"{eid}: required_slices must match protected slices")
  revision=row.get("code_revision")
  started=row.get("started_at");finished=row.get("finished_at")
  refs=row.get("run_manifest_refs")
  checkpoint_ids=row.get("checkpoint_ids")
  if not isinstance(checkpoint_ids,list) or len(checkpoint_ids)!=len(set(checkpoint_ids)):fail(f"{eid}: checkpoint_ids must be a unique list")
  if not isinstance(refs,list):fail(f"{eid}: run_manifest_refs must be a list")
  for ref in refs:
   if not isinstance(ref,dict) or set(ref)!={"path","sha256"}:fail(f"{eid}: run manifest ref must contain path and sha256")
   if not isinstance(ref["path"],str) or not ref["path"].startswith("model_tuning/runs/"):fail(f"{eid}: run manifest path must be under model_tuning/runs/")
   if not SHA256.fullmatch(str(ref["sha256"])):fail(f"{eid}: run manifest sha256 invalid")
  outcome=row.get("outcome")
  if not isinstance(outcome,dict) or set(outcome)!={"promotion_eligible","failure_stage","reason"}:fail(f"{eid}: outcome must contain promotion_eligible, failure_stage, reason")
  if outcome.get("promotion_eligible") is not False:fail(f"{eid}: registry may never authorize promotion")
  if status in {"planned","blocked"}:
   if revision is not None or started is not None or finished is not None or refs or checkpoint_ids:fail(f"{eid}: unstarted experiment must not claim runtime/checkpoint provenance")
   if status=="blocked" and not str(outcome.get("reason") or "").strip():fail(f"{eid}: blocked experiment requires reason")
  else:
   if not isinstance(revision,str) or not SHA40.fullmatch(revision):fail(f"{eid}: started experiment requires exact code_revision")
   if not isinstance(started,str) or not started.strip():fail(f"{eid}: started experiment requires started_at")
  if status=="running":
   if finished is not None:fail(f"{eid}: running experiment cannot have finished_at")
  if status in {"succeeded","failed","aborted","reviewed"}:
   if not isinstance(finished,str) or not finished.strip():fail(f"{eid}: terminal experiment requires finished_at")
  if status in {"succeeded","reviewed"} and not refs:fail(f"{eid}: successful/reviewed experiment requires run manifest refs")
  if kind in {"qlora","adapter_eval","adapter_combination"} and status in {"succeeded","reviewed"} and not checkpoint_ids:fail(f"{eid}: successful adapter experiment requires checkpoint_ids")
  if status in {"failed","aborted"}:
   if not str(outcome.get("failure_stage") or "").strip():fail(f"{eid}: failed/aborted experiment requires failure_stage")
   if not str(outcome.get("reason") or "").strip():fail(f"{eid}: failed/aborted experiment requires reason")
  pref=row.get("promotion_decision_ref")
  if pref is not None:
   if not isinstance(pref,dict) or set(pref)!={"path","sha256"}:fail(f"{eid}: promotion_decision_ref must contain path and sha256")
   if not isinstance(pref["path"],str) or not pref["path"].startswith("model_tuning/reviews/"):fail(f"{eid}: promotion decision must live under model_tuning/reviews/")
   if not SHA256.fullmatch(str(pref["sha256"])):fail(f"{eid}: promotion decision sha256 invalid")

def validate(path=DEFAULT):
 validate_doc(load(path),load(TASKS),load(CANDIDATES))

def self_test():
 tasks={"tasks":[{"id":"GD-COMPUTE-001","lane":"compute"}]}
 candidates={"candidates":[{"id":"qwen3-8b-primary"}]}
 base={"schema_version":"grow-doc-experiment-registry-v1","policy":{"append_only_intent":True,"retain_failed_and_aborted_runs":True,"registry_never_authorizes_promotion":True,"required_protected_slices":sorted(REQUIRED_SLICES)},"experiments":[{"experiment_id":"e1","task_id":"GD-COMPUTE-001","kind":"base_vs_rag","status":"blocked","candidate_ids":["qwen3-8b-primary"],"code_revision":None,"benchmark_path":"model_tuning/eval/heldout_v3.jsonl","required_slices":sorted(REQUIRED_SLICES),"started_at":None,"finished_at":None,"run_manifest_refs":[],"checkpoint_ids":[],"promotion_decision_ref":None,"outcome":{"promotion_eligible":False,"failure_stage":None,"reason":"no gpu"}}]}
 validate_doc(base,tasks,candidates)
 bad=json.loads(json.dumps(base));bad["experiments"][0]["outcome"]["promotion_eligible"]=True
 try:validate_doc(bad,tasks,candidates)
 except ValueError:pass
 else:raise AssertionError("registry promotion authorization must fail")
 failed=json.loads(json.dumps(base));r=failed["experiments"][0];r.update(status="failed",code_revision="a"*40,started_at="2026-01-01T00:00:00Z",finished_at="2026-01-01T00:01:00Z");r["outcome"]={"promotion_eligible":False,"failure_stage":"preflight","reason":"CUDA unavailable"}
 validate_doc(failed,tasks,candidates)
 failed["experiments"][0]["outcome"]["failure_stage"]=None
 try:validate_doc(failed,tasks,candidates)
 except ValueError:pass
 else:raise AssertionError("failed experiment without failure stage must fail")
 print("Grow Doc experiment registry self-test: PASS")

def main():
 p=argparse.ArgumentParser();p.add_argument("--registry",type=pathlib.Path,default=DEFAULT);p.add_argument("--self-test",action="store_true");a=p.parse_args()
 try:
  if a.self_test:self_test()
  else:validate(a.registry);print(f"Grow Doc experiment registry: PASS ({a.registry})")
 except (OSError,json.JSONDecodeError,ValueError) as exc:
  print(f"Grow Doc experiment registry: FAIL: {exc}");return 2
 return 0
if __name__=="__main__":raise SystemExit(main())
