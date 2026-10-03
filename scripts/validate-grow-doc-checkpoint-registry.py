#!/usr/bin/env python3
"""Validate immutable Grow Doc checkpoint/artifact provenance."""
from __future__ import annotations
import argparse,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT=ROOT/"model_tuning/checkpoints/registry_v1.json"
EXPERIMENTS=ROOT/"model_tuning/experiments/registry_v1.json"
CANDIDATES=ROOT/"model_tuning/config/base_model_candidates_v1.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
SHA64=re.compile(r"^[0-9a-f]{64}$")
STATUSES={"candidate","rejected","reviewed"}
KINDS={"lora_adapter","merged_adapter","model_soup"}

def fail(msg): raise ValueError(msg)
def load(path): return json.loads(path.read_text(encoding="utf-8"))

def validate_doc(data, experiments, candidates):
    if data.get("schema_version")!="grow-doc-checkpoint-registry-v1":
        fail("unsupported checkpoint registry schema")
    policy=data.get("policy") or {}
    for key in (
        "retain_rejected_and_failed_artifacts",
        "require_exact_artifact_sha256",
        "require_training_snapshot_sha256",
        "require_config_sha256",
        "require_code_revision",
        "require_runtime_hardware_provenance",
        "registry_never_authorizes_promotion",
    ):
        if policy.get(key) is not True:
            fail(f"policy {key} must be true")
    exp_map={x["experiment_id"]:x for x in experiments.get("experiments",[])}
    candidate_map={x["id"]:x for x in candidates.get("candidates",[])}
    rows=data.get("checkpoints")
    if not isinstance(rows,list):
        fail("checkpoints must be a list")
    seen=set()
    for row in rows:
        cid=row.get("checkpoint_id")
        if not isinstance(cid,str) or not cid.strip() or cid in seen:
            fail(f"invalid or duplicate checkpoint_id: {cid!r}")
        seen.add(cid)
        status=row.get("status")
        if status not in STATUSES:
            fail(f"{cid}: invalid checkpoint status")
        kind=row.get("kind")
        if kind not in KINDS:
            fail(f"{cid}: invalid checkpoint kind")
        eid=row.get("experiment_id")
        exp=exp_map.get(eid)
        if exp is None:
            fail(f"{cid}: unknown experiment_id {eid}")
        if exp.get("status") in {"planned","blocked","running","failed","aborted"}:
            fail(f"{cid}: experiment must be succeeded or reviewed before checkpoint registration")
        code=row.get("code_revision")
        if not isinstance(code,str) or not SHA40.fullmatch(code):
            fail(f"{cid}: exact code_revision required")
        if exp.get("code_revision")!=code:
            fail(f"{cid}: code_revision must match experiment")

        base=row.get("base_model") or {}
        candidate_id=base.get("candidate_id")
        if candidate_id not in candidate_map:
            fail(f"{cid}: unknown base_model candidate_id")
        if base.get("repository")!=candidate_map[candidate_id].get("repo_id"):
            fail(f"{cid}: base_model repository differs from candidate registry")
        revision=base.get("revision")
        if not isinstance(revision,str) or not SHA40.fullmatch(revision):
            fail(f"{cid}: base_model revision must be exact 40-char SHA")

        artifact=row.get("artifact") or {}
        if set(artifact)!={"storage_uri","revision","sha256","bytes"}:
            fail(f"{cid}: artifact must contain storage_uri, revision, sha256, bytes")
        if not isinstance(artifact["storage_uri"],str) or not artifact["storage_uri"].strip():
            fail(f"{cid}: artifact storage_uri required")
        if not isinstance(artifact["revision"],str) or not SHA40.fullmatch(artifact["revision"]):
            fail(f"{cid}: artifact revision must be exact 40-char SHA")
        if not isinstance(artifact["sha256"],str) or not SHA64.fullmatch(artifact["sha256"]):
            fail(f"{cid}: artifact sha256 invalid")
        if isinstance(artifact["bytes"],bool) or not isinstance(artifact["bytes"],int) or artifact["bytes"]<=0:
            fail(f"{cid}: artifact bytes must be positive integer")

        training=row.get("training") or {}
        required_training={"snapshot_manifest_sha256","config_path","config_sha256","dependency_lock_sha256","seed"}
        if set(training)!=required_training:
            fail(f"{cid}: training provenance must contain exactly {sorted(required_training)}")
        for key in ("snapshot_manifest_sha256","config_sha256","dependency_lock_sha256"):
            if not isinstance(training[key],str) or not SHA64.fullmatch(training[key]):
                fail(f"{cid}: training {key} invalid")
        if training["config_path"]!="model_tuning/config/qlora_8b.yaml":
            fail(f"{cid}: unexpected training config_path")
        if isinstance(training["seed"],bool) or not isinstance(training["seed"],int):
            fail(f"{cid}: training seed must be integer")

        runtime=row.get("runtime") or {}
        required_runtime={"python","torch","transformers","peft","bitsandbytes","accelerate","cuda","gpu_name","gpu_memory_bytes","compute_capability"}
        if set(runtime)!=required_runtime:
            fail(f"{cid}: runtime provenance must contain exactly {sorted(required_runtime)}")
        for key in ("python","torch","transformers","peft","bitsandbytes","accelerate","cuda","gpu_name","compute_capability"):
            if not isinstance(runtime[key],str) or not runtime[key].strip():
                fail(f"{cid}: runtime {key} required")
        if isinstance(runtime["gpu_memory_bytes"],bool) or not isinstance(runtime["gpu_memory_bytes"],int) or runtime["gpu_memory_bytes"]<=0:
            fail(f"{cid}: gpu_memory_bytes must be positive integer")

        evaluation=row.get("evaluation") or {}
        refs=evaluation.get("run_manifest_refs")
        if not isinstance(refs,list) or not refs:
            fail(f"{cid}: at least one evaluation run manifest ref required")
        for ref in refs:
            if not isinstance(ref,dict) or set(ref)!={"path","sha256"}:
                fail(f"{cid}: evaluation ref must contain path and sha256")
            if not isinstance(ref["path"],str) or not ref["path"].startswith("model_tuning/runs/"):
                fail(f"{cid}: evaluation run manifest must live under model_tuning/runs/")
            if not isinstance(ref["sha256"],str) or not SHA64.fullmatch(ref["sha256"]):
                fail(f"{cid}: evaluation run manifest sha256 invalid")
        decision=evaluation.get("promotion_decision_ref")
        if decision is not None:
            if not isinstance(decision,dict) or set(decision)!={"path","sha256"}:
                fail(f"{cid}: promotion decision ref must contain path and sha256")
            if not decision["path"].startswith("model_tuning/reviews/") or not SHA64.fullmatch(str(decision["sha256"])):
                fail(f"{cid}: promotion decision ref invalid")

        disposition=row.get("disposition") or {}
        if set(disposition)!={"promotion_eligible","reason"}:
            fail(f"{cid}: disposition must contain promotion_eligible and reason")
        if disposition["promotion_eligible"] is not False:
            fail(f"{cid}: checkpoint registry may never authorize promotion")
        if not isinstance(disposition["reason"],str) or not disposition["reason"].strip():
            fail(f"{cid}: disposition reason required")
        if status=="reviewed" and decision is None:
            fail(f"{cid}: reviewed checkpoint requires promotion decision ref")

def validate(path=DEFAULT):
    validate_doc(load(path),load(EXPERIMENTS),load(CANDIDATES))

def self_test():
    experiments={"experiments":[{"experiment_id":"e1","status":"succeeded","code_revision":"a"*40}]}
    candidates={"candidates":[{"id":"qwen","repo_id":"Qwen/Qwen3-8B"}]}
    good={
      "schema_version":"grow-doc-checkpoint-registry-v1",
      "policy":{
        "retain_rejected_and_failed_artifacts":True,
        "require_exact_artifact_sha256":True,
        "require_training_snapshot_sha256":True,
        "require_config_sha256":True,
        "require_code_revision":True,
        "require_runtime_hardware_provenance":True,
        "registry_never_authorizes_promotion":True,
      },
      "checkpoints":[{
        "checkpoint_id":"cp1","experiment_id":"e1","status":"candidate","kind":"lora_adapter",
        "code_revision":"a"*40,
        "base_model":{"candidate_id":"qwen","repository":"Qwen/Qwen3-8B","revision":"b"*40},
        "artifact":{"storage_uri":"hf://dtf/cp","revision":"c"*40,"sha256":"d"*64,"bytes":123},
        "training":{"snapshot_manifest_sha256":"e"*64,"config_path":"model_tuning/config/qlora_8b.yaml","config_sha256":"f"*64,"dependency_lock_sha256":"1"*64,"seed":420},
        "runtime":{"python":"3.12","torch":"x","transformers":"x","peft":"x","bitsandbytes":"x","accelerate":"x","cuda":"x","gpu_name":"GPU","gpu_memory_bytes":1,"compute_capability":"8.0"},
        "evaluation":{"run_manifest_refs":[{"path":"model_tuning/runs/x/run-manifest.json","sha256":"2"*64}],"promotion_decision_ref":None},
        "disposition":{"promotion_eligible":False,"reason":"awaiting review"}
      }]
    }
    validate_doc(good,experiments,candidates)
    bad=json.loads(json.dumps(good));bad["checkpoints"][0]["disposition"]["promotion_eligible"]=True
    try: validate_doc(bad,experiments,candidates)
    except ValueError: pass
    else: raise AssertionError("registry promotion authorization must fail")
    bad=json.loads(json.dumps(good));bad["checkpoints"][0]["experiment_id"]="missing"
    try: validate_doc(bad,experiments,candidates)
    except ValueError: pass
    else: raise AssertionError("unknown experiment must fail")
    print("Grow Doc checkpoint registry self-test: PASS")

def main():
    p=argparse.ArgumentParser();p.add_argument("--registry",type=pathlib.Path,default=DEFAULT);p.add_argument("--self-test",action="store_true");a=p.parse_args()
    try:
        if a.self_test:self_test()
        else:validate(a.registry);print(f"Grow Doc checkpoint registry: PASS ({a.registry})")
    except (OSError,json.JSONDecodeError,ValueError) as exc:
        print(f"Grow Doc checkpoint registry: FAIL: {exc}");return 2
    return 0
if __name__=="__main__":raise SystemExit(main())
