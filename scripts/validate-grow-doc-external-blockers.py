#!/usr/bin/env python3
"""Validate external-blocker operator artifacts remain fail-closed."""
from __future__ import annotations
import argparse,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/"dataset/acquisition/supervised-vision-intake-template.json"
COMPLETION=ROOT/"model_tuning/project_completion_v1.json"

def fail(msg): raise ValueError(msg)
def validate_template():
    d=json.loads(TEMPLATE.read_text(encoding="utf-8"))
    if d.get("schema_version")!="grow-doc-supervised-vision-intake-v1":
        fail("unexpected vision intake template schema")
    if d.get("status")!="draft":
        fail("vision intake template must remain draft")
    s=d.get("sample") or {}
    if s.get("trainingEligible") is not False:
        fail("vision intake template must default trainingEligible=false")
    if s.get("splitStatus")!="unassigned":
        fail("vision intake template must default splitStatus=unassigned")
    rights=s.get("rights") or {}
    if rights.get("trainingPermission")!="unknown":
        fail("vision intake template must not presume training rights")
    review=s.get("review") or {}
    if any(review.get(k)!="pending" for k in ("scientificReview","rightsReview","annotationReview")):
        fail("vision intake reviews must default pending")
    checks=d.get("admission_checks") or {}
    if not checks or any(v is not False for v in checks.values()):
        fail("all vision admission checks must default false")
    p=d.get("policy") or {}
    for key in ("cannot_promote_from_visual_symptoms_alone","cannot_promote_cross_crop_as_cannabis_ground_truth","cannot_promote_without_training_permission"):
        if p.get(key) is not True:
            fail(f"vision intake policy {key} must remain true")

def validate_completion_links():
    d=json.loads(COMPLETION.read_text(encoding="utf-8"))
    ids={x.get("id") for x in d.get("external_blockers",[])}
    if ids!={"EXT-GOV-001","EXT-COMPUTE-001","EXT-VISION-001","EXT-DEPLOY-001"}:
        fail("completion manifest external blockers drifted")

def self_test():
    validate_template();validate_completion_links()
    print("Grow Doc external blocker artifacts self-test: PASS")

def main():
    p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");a=p.parse_args()
    try:
        validate_template();validate_completion_links()
        if a.self_test:self_test()
        else:print("Grow Doc external blocker artifacts: PASS")
    except (OSError,json.JSONDecodeError,ValueError) as exc:
        print(f"Grow Doc external blocker artifacts: FAIL: {exc}");return 2
    return 0
if __name__=="__main__":raise SystemExit(main())
