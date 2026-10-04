#!/usr/bin/env python3
import json, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
q=json.loads((ROOT/"dataset/automation/global_work_queue_v1.json").read_text())
items={x["work_item_id"]:x for x in q["items"]}
def score(x):
 p=x["priority_inputs"]; return p["products_unlocked"]*p["severity"]*p["evidence_readiness"]*p["expected_coverage_gain"]/p["estimated_effort"]
def deps_done(x): return all(items.get(d,{}).get("status")=="done" for d in x.get("dependencies",[]))
eligible=[x for x in q["items"] if x["status"]=="ready" and deps_done(x)]
eligible.sort(key=lambda x:(-score(x),x["work_item_id"]))
print(json.dumps([{"work_item_id":x["work_item_id"],"worker":x["worker"],"score":score(x),"next_action":x["checkpoint"]["next_action"]} for x in eligible],indent=2))
