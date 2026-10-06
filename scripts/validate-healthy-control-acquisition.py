#!/usr/bin/env python3
"""Validate fail-closed healthy-control acquisition planning."""
from __future__ import annotations
import json,pathlib,re,sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
PLAN=ROOT/"dataset/acquisition/healthy-control-extraction-plan-v1.json"
DOI=re.compile(r"^doi:10\.\d{4,9}/\S+$",re.I)

def fail(message): raise ValueError(message)

def validate(doc):
    if doc.get("schema_version")!="grow-doc-healthy-control-acquisition-plan-v1":
        fail("unsupported healthy-control acquisition schema")
    policy=doc.get("policy") or {}
    required=[
      "no_visual_inference_of_health_or_diagnosis",
      "source_authored_control_or_comparison_label_required",
      "exact_child_asset_rights_required",
      "source_group_isolation_required",
      "sha256_and_perceptual_hash_required",
      "human_scientific_review_required",
      "generated_plan_never_grants_training_eligibility",
    ]
    if any(policy.get(key) is not True for key in required):
        fail("all fail-closed acquisition policies must remain true")
    rows=doc.get("work_items")
    if not isinstance(rows,list) or len(rows)<2: fail("at least two controlled work items required")
    ids=set()
    for row in rows:
        rid=row.get("id")
        if not isinstance(rid,str) or not rid or rid in ids: fail(f"invalid or duplicate work item id: {rid!r}")
        ids.add(rid)
        if row.get("training_eligible") is not False or row.get("locked_evaluation_eligible") is not False:
            fail(f"{rid}: planning may never grant training/evaluation eligibility")
        if not DOI.fullmatch(str(row.get("persistent_id") or "")): fail(f"{rid}: persistent DOI required")
        if not str(row.get("canonical_source") or "").startswith("https://"): fail(f"{rid}: HTTPS source required")
        if not row.get("target_material") or not row.get("required_steps"): fail(f"{rid}: target material and required steps required")
        steps=" ".join(row["required_steps"]).lower()
        for token in ("sha-256","sourcegroupid","human"):
            if token not in steps: fail(f"{rid}: required provenance/review step missing: {token}")
    return len(rows)

def main():
    try:
        count=validate(json.loads(PLAN.read_text(encoding="utf-8")))
        print(f"Grow Doc healthy-control acquisition plan: PASS ({count} work items)")
        return 0
    except (OSError,json.JSONDecodeError,ValueError) as exc:
        print(f"Grow Doc healthy-control acquisition plan: FAIL: {exc}")
        return 2

if __name__=="__main__": raise SystemExit(main())
