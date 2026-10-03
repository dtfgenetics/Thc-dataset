#!/usr/bin/env python3
"""Validate the persistent Grow Doc autonomous-engineer state file."""
from __future__ import annotations
import argparse, json, re, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/".agents/state/grow-doc.json"
HEX40=re.compile(r"^[0-9a-f]{40}$")
STATUSES={"active","blocked_external","blocked_repo","ready_for_ci","ready_for_merge","complete"}

def validate(doc:dict)->list[str]:
    errors=[]
    required=("schema_version","updated_at","last_verified_main_sha","current_work_item","status","completed","dataset_counts_or_eval_metrics","next_action")
    for key in required:
        if key not in doc: errors.append(f"missing required field: {key}")
    if doc.get("schema_version")!="grow-doc-agent-state-v1": errors.append("unsupported schema_version")
    if not HEX40.fullmatch(str(doc.get("last_verified_main_sha",""))): errors.append("last_verified_main_sha must be a 40-char lowercase git SHA")
    if doc.get("status") not in STATUSES: errors.append("invalid status")
    if not str(doc.get("current_work_item","")).strip(): errors.append("current_work_item required")
    if not str(doc.get("next_action","")).strip(): errors.append("next_action required")
    completed=doc.get("completed")
    if not isinstance(completed,list): errors.append("completed must be a list")
    else:
        ids=[]
        for i,item in enumerate(completed,1):
            if not isinstance(item,dict): errors.append(f"completed[{i}] must be an object"); continue
            cid=str(item.get("id","")).strip()
            if not cid: errors.append(f"completed[{i}].id required")
            ids.append(cid)
            if item.get("merged_sha") is not None and not HEX40.fullmatch(str(item["merged_sha"])): errors.append(f"completed[{i}].merged_sha invalid")
        if len(ids)!=len(set(ids)): errors.append("completed ids must be unique")
    if doc.get("status")=="blocked_external":
        blocker=doc.get("blocker")
        if not isinstance(blocker,dict) or not str(blocker.get("reason","")).strip(): errors.append("blocked_external requires blocker.reason")
    return errors

def self_test():
    good={"schema_version":"grow-doc-agent-state-v1","updated_at":"2026-01-01T00:00:00Z","last_verified_main_sha":"a"*40,"current_work_item":"x","status":"active","completed":[],"dataset_counts_or_eval_metrics":{},"next_action":"y"}
    assert not validate(good)
    assert validate({**good,"status":"blocked_external"})
    assert validate({**good,"last_verified_main_sha":"bad"})
    assert validate({**good,"completed":[{"id":"x"},{"id":"x"}]})
    print("Grow Doc agent state self-test: PASS")

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path,default=DEFAULT); ap.add_argument("--self-test",action="store_true"); args=ap.parse_args()
    if args.self_test: self_test(); return 0
    doc=json.loads(args.input.read_text(encoding="utf-8"))
    errors=validate(doc)
    print(json.dumps({"ok":not errors,"errors":errors},indent=2))
    return 0 if not errors else 2

if __name__=="__main__": raise SystemExit(main())
