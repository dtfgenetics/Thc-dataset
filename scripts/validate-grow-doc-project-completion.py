#!/usr/bin/env python3
"""Validate Grow Doc project-completion claims against canonical repository state."""
from __future__ import annotations
import argparse,json,pathlib,re,subprocess

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT=ROOT/"model_tuning/project_completion_v1.json"
EXPERIMENTS=ROOT/"model_tuning/experiments/registry_v1.json"
READINESS=ROOT/"data/model-training-readiness.json"
CHECKPOINTS=ROOT/"model_tuning/checkpoints/registry_v1.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
EXPECTED_CONTROLS={
 "reviewed-rag-publication",
 "source-provenance-and-rights-gates",
 "strong-evidence-sft-and-grounded-qa",
 "heldout-protected-slices",
 "dedup-near-duplicate-and-leakage-gates",
 "supervision-concentration-gate",
 "qlora-config-runtime-and-artifact-freeze",
 "base-model-candidate-registry",
 "adapter-combination-policy",
 "contribution-task-receipt-history-system",
 "experiment-registry",
 "checkpoint-artifact-registry",
 "gpu-workflow-exact-main-sha-gate",
}
EXPECTED_EXTERNAL={"EXT-GOV-001","EXT-COMPUTE-001","EXT-VISION-001","EXT-DEPLOY-001"}
EXPECTED_ISSUES={"EXT-GOV-001":398,"EXT-COMPUTE-001":399,"EXT-VISION-001":400,"EXT-DEPLOY-001":95}

def fail(msg): raise ValueError(msg)
def load(path): return json.loads(path.read_text(encoding="utf-8"))

def validate_doc(doc, experiments, readiness, checkpoints):
    if doc.get("schema_version")!="grow-doc-project-completion-v1":
        fail("unsupported project completion schema")
    sha=doc.get("audited_main_sha")
    if not isinstance(sha,str) or not SHA40.fullmatch(sha):
        fail("audited_main_sha must be an exact lowercase 40-character SHA")
    if doc.get("status")!="engineering-complete-external-blockers-remain":
        fail("status must remain engineering-complete-external-blockers-remain while blockers exist")
    controls=doc.get("completed_controls")
    if set(controls or [])!=EXPECTED_CONTROLS or len(controls)!=len(set(controls)):
        fail("completed_controls must exactly match the locked engineering control set")
    blockers=doc.get("external_blockers")
    if not isinstance(blockers,list) or {x.get("id") for x in blockers}!=EXPECTED_EXTERNAL:
        fail("external_blockers must contain governance, compute, vision, and deployment blockers")
    by_id={x["id"]:x for x in blockers}
    for bid,item in by_id.items():
        if item.get("state")!="blocked":
            fail(f"{bid}: state must remain blocked until its external completion criteria are actually met")
        if not str(item.get("owner") or "").strip():
            fail(f"{bid}: owner required")
        if not str(item.get("evidence") or "").strip():
            fail(f"{bid}: evidence required")
        criteria=item.get("completion_criteria")
        if not isinstance(criteria,list) or not criteria or any(not str(x).strip() for x in criteria):
            fail(f"{bid}: non-empty completion_criteria required")
        issue=item.get("tracking_issue")
        number=EXPECTED_ISSUES[bid]
        expected_url=f"https://github.com/dtfgenetics/Thc-dataset/issues/{number}"
        if not isinstance(issue,dict) or issue.get("number")!=number or issue.get("url")!=expected_url:
            fail(f"{bid}: tracking_issue must point to #{number}")

    exp=next((x for x in experiments.get("experiments",[]) if x.get("experiment_id")=="exp-qwen3-8b-base-vs-rag-001"),None)
    if exp is None:
        fail("missing canonical base-vs-RAG experiment")
    if exp.get("status")!="blocked":
        fail("completion manifest must be updated when canonical compute experiment leaves blocked state")
    if by_id["EXT-COMPUTE-001"].get("state")!="blocked":
        fail("compute blocker disagrees with experiment registry")

    vision=(readiness.get("visionLayer") or {})
    eligible=vision.get("trainingEligibleSamples")
    ready=readiness.get("readyForSupervisedCannabisDiagnosisTraining")
    if eligible!=0 or ready is not False:
        fail("completion manifest must be updated when supervised vision eligibility changes")
    if by_id["EXT-VISION-001"].get("state")!="blocked":
        fail("vision blocker disagrees with readiness manifest")

    if checkpoints.get("schema_version")!="grow-doc-checkpoint-registry-v1":
        fail("checkpoint registry missing or incompatible")

    prohibited=doc.get("prohibited_claims_until_unblocked")
    required_prohibited={
      "RAG benchmark improvement","QLoRA training success","checkpoint superiority",
      "adapter promotion","adapter merge or model soup success",
      "supervised vision readiness","model deployment"
    }
    if set(prohibited or [])!=required_prohibited:
        fail("prohibited_claims_until_unblocked must match locked claim boundary")

def validate_audit_ancestry(doc):
    sha=doc["audited_main_sha"]
    try:
        subprocess.run(["git","cat-file","-e",f"{sha}^{{commit}}"],cwd=ROOT,check=True,capture_output=True,text=True)
        result=subprocess.run(["git","merge-base","--is-ancestor",sha,"HEAD"],cwd=ROOT,capture_output=True,text=True)
    except OSError as exc:
        fail(f"unable to verify audited_main_sha in Git history: {exc}")
    if result.returncode!=0:
        fail("audited_main_sha is not an ancestor of current HEAD")

def validate(path=DEFAULT):
    doc=load(path)
    validate_doc(doc,load(EXPERIMENTS),load(READINESS),load(CHECKPOINTS))
    validate_audit_ancestry(doc)

def self_test():
    doc={
      "schema_version":"grow-doc-project-completion-v1",
      "audited_main_sha":"a"*40,
      "status":"engineering-complete-external-blockers-remain",
      "completed_controls":sorted(EXPECTED_CONTROLS),
      "external_blockers":[
        {"id":"EXT-GOV-001","state":"blocked","owner":"admin","evidence":"none","completion_criteria":["protect"],"tracking_issue":{"number":398,"url":"https://github.com/dtfgenetics/Thc-dataset/issues/398"}},
        {"id":"EXT-COMPUTE-001","state":"blocked","owner":"gpu","evidence":"blocked","completion_criteria":["run"],"tracking_issue":{"number":399,"url":"https://github.com/dtfgenetics/Thc-dataset/issues/399"}},
        {"id":"EXT-VISION-001","state":"blocked","owner":"data","evidence":"0","completion_criteria":["collect"],"tracking_issue":{"number":400,"url":"https://github.com/dtfgenetics/Thc-dataset/issues/400"}},
        {"id":"EXT-DEPLOY-001","state":"blocked","owner":"deploy","evidence":"secrets unavailable","completion_criteria":["restore and deploy"],"tracking_issue":{"number":95,"url":"https://github.com/dtfgenetics/Thc-dataset/issues/95"}},
      ],
      "non_blocking_continuous_work":[],
      "prohibited_claims_until_unblocked":[
        "RAG benchmark improvement","QLoRA training success","checkpoint superiority",
        "adapter promotion","adapter merge or model soup success",
        "supervised vision readiness","model deployment"
      ],
    }
    experiments={"experiments":[{"experiment_id":"exp-qwen3-8b-base-vs-rag-001","status":"blocked"}]}
    readiness={"readyForSupervisedCannabisDiagnosisTraining":False,"visionLayer":{"trainingEligibleSamples":0}}
    checkpoints={"schema_version":"grow-doc-checkpoint-registry-v1","checkpoints":[]}
    validate_doc(doc,experiments,readiness,checkpoints)
    bad=json.loads(json.dumps(doc));bad["external_blockers"][1]["state"]="complete"
    try: validate_doc(bad,experiments,readiness,checkpoints)
    except ValueError: pass
    else: raise AssertionError("false compute completion must fail")
    bad_readiness={"readyForSupervisedCannabisDiagnosisTraining":True,"visionLayer":{"trainingEligibleSamples":1}}
    try:
        validate_doc(doc,experiments,bad_readiness,checkpoints)
    except ValueError as exc:
        assert "vision eligibility changes" in str(exc)
    else:
        raise AssertionError("false vision completion must fail")
    bad_experiments={"experiments":[{"experiment_id":"exp-qwen3-8b-base-vs-rag-001","status":"succeeded"}]}
    try:
        validate_doc(doc,bad_experiments,readiness,checkpoints)
    except ValueError as exc:
        assert "experiment leaves blocked state" in str(exc)
    else:
        raise AssertionError("stale compute blocker must fail after experiment status changes")
    print("Grow Doc project completion self-test: PASS")

def main():
    p=argparse.ArgumentParser();p.add_argument("--manifest",type=pathlib.Path,default=DEFAULT);p.add_argument("--self-test",action="store_true");a=p.parse_args()
    try:
        if a.self_test:self_test()
        else:validate(a.manifest);print(f"Grow Doc project completion audit: PASS ({a.manifest})")
    except (OSError,json.JSONDecodeError,ValueError) as exc:
        print(f"Grow Doc project completion audit: FAIL: {exc}");return 2
    return 0
if __name__=="__main__":raise SystemExit(main())
