#!/usr/bin/env python3
"""Fail closed when Grow Doc README frozen-contract documentation drifts from executable artifacts."""
from __future__ import annotations
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
README=ROOT/"model_tuning/README.md"
CONFIG=ROOT/"model_tuning/config/qlora_8b.yaml"
LOCK=ROOT/"model_tuning/generated/training_artifact_lock_v3.json"

def scalar(text,key):
 m=re.search(rf"(?m)^\s*{re.escape(key)}:\s*([^#\n]+?)\s*$",text)
 return m.group(1).strip().strip("'\"") if m else None

def readme_value(text,label):
 m=re.search(rf"- {re.escape(label)}: `([0-9a-f]+)`",text)
 return m.group(1) if m else None

def readme_mixture(text):
 m=re.search(r"- current frozen training mixture: (\d+) SFT \+ (\d+) grounded-QA = (\d+) rows \(~([0-9.]+)% grounded-QA\)",text)
 return tuple(map(float,m.groups())) if m else None

def validate():
 errors=[]
 rt=README.read_text(encoding="utf-8")
 ct=CONFIG.read_text(encoding="utf-8")
 cfg_split=scalar(ct,"split_manifest_sha256")
 cfg_dataset=scalar(ct,"dataset_manifest_sha256")
 doc_split=readme_value(rt,"training split manifest SHA-256")
 doc_dataset=readme_value(rt,"training dataset manifest SHA-256")
 if doc_split!=cfg_split: errors.append(f"README split hash drift: {doc_split} != {cfg_split}")
 if doc_dataset!=cfg_dataset: errors.append(f"README dataset hash drift: {doc_dataset} != {cfg_dataset}")
 if LOCK.exists():
  lock=json.loads(LOCK.read_text(encoding="utf-8"))
  if lock.get("training_split_manifest_sha256")!=cfg_split: errors.append("generated lock split hash disagrees with QLoRA config")
  if lock.get("training_dataset_manifest_sha256")!=cfg_dataset: errors.append("generated lock dataset hash disagrees with QLoRA config")
  mix=readme_mixture(rt)
  if not mix: errors.append("README frozen mixture line missing or malformed")
  else:
   doc_sft,doc_gqa,doc_total,doc_pct=mix
   total=int(lock.get("training_rows",-1)); gqa=int(lock.get("grounded_qa_selected_rows",-1)); sft=total-gqa
   pct=round(float(lock.get("grounded_qa_fraction",0))*100,1)
   if (int(doc_sft),int(doc_gqa),int(doc_total))!=(sft,gqa,total):
    errors.append(f"README mixture counts drift: {(int(doc_sft),int(doc_gqa),int(doc_total))} != {(sft,gqa,total)}")
   if abs(doc_pct-pct)>0.05: errors.append(f"README grounded-QA percentage drift: {doc_pct} != {pct}")
 return errors

def self_test():
 text="- training split manifest SHA-256: `"+("a"*64)+"`\n- training dataset manifest SHA-256: `"+("b"*64)+"`\n- current frozen training mixture: 8 SFT + 2 grounded-QA = 10 rows (~20.0% grounded-QA)\n"
 assert readme_value(text,"training split manifest SHA-256")=="a"*64
 assert readme_value(text,"training dataset manifest SHA-256")=="b"*64
 assert readme_mixture(text)==(8.0,2.0,10.0,20.0)
 print("Grow Doc README contract self-test: PASS")

if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");a=p.parse_args()
 if a.self_test:self_test();raise SystemExit(0)
 errs=validate()
 print(json.dumps({"ok":not errs,"errors":errs},indent=2))
 raise SystemExit(0 if not errs else 2)
