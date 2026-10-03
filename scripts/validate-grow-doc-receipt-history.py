#!/usr/bin/env python3
"""Verify integrated Grow Doc receipts against durable Git history."""
from __future__ import annotations
import argparse,json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]

def git(root,*args,check=True):
 p=subprocess.run(["git",*args],cwd=root,text=True,capture_output=True)
 if check and p.returncode: raise ValueError((p.stderr or p.stdout).strip() or f"git {' '.join(args)} failed")
 return p

def exact_sha(value,label):
 if not isinstance(value,str) or len(value)!=40 or any(c not in "0123456789abcdef" for c in value):
  raise ValueError(f"{label} must be exact lowercase 40-character Git SHA")
 return value

def diff_paths(root,base,head):
 out=git(root,"diff","--name-only","--diff-filter=ACMRTUXB",base,head).stdout
 return sorted(x.strip() for x in out.splitlines() if x.strip())

def validate_receipt(path,root=ROOT):
 r=json.loads(path.read_text(encoding="utf-8"));integration=r.get("integration")
 if integration is None:return {"receipt":path.name,"integrated":False,"verified":False}
 commit=exact_sha(integration.get("commit"),"integration.commit")
 base=exact_sha(r.get("base_commit"),"base_commit")
 git(root,"cat-file","-e",f"{commit}^{{commit}}")
 parents=git(root,"show","-s","--format=%P",commit).stdout.strip().split()
 if integration.get("method")=="squash":
  if len(parents)!=1:raise ValueError(f"{path.name}: squash integration must have exactly one parent")
  if parents[0]!=base:raise ValueError(f"{path.name}: integration parent {parents[0]} != receipt base {base}")
  actual=diff_paths(root,parents[0],commit)
 else:
  if base not in parents and not git(root,"merge-base","--is-ancestor",base,commit,check=False).returncode==0:
   raise ValueError(f"{path.name}: integration commit is not descended from receipt base")
  actual=diff_paths(root,base,commit)
 expected=sorted(r.get("changed_paths") or [])
 if actual!=expected:raise ValueError(f"{path.name}: integrated Git diff paths {actual} != receipt changed_paths {expected}")
 return {"receipt":path.name,"integrated":True,"verified":True,"integration_commit":commit,"changed_paths":len(actual)}

def validate_dir(path,root=ROOT):
 reports=[];errors=[]
 for p in sorted(path.glob("*.json")):
  try:reports.append(validate_receipt(p,root))
  except (OSError,ValueError,json.JSONDecodeError) as exc:errors.append(f"{p.name}: {exc}")
 return reports,errors

def self_test():
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);git(root,"init","-q");git(root,"config","user.email","fixture@example.test");git(root,"config","user.name","Fixture")
  (root/"a.txt").write_text("a\n");git(root,"add","a.txt");git(root,"commit","-qm","base");base=git(root,"rev-parse","HEAD").stdout.strip()
  (root/"x.txt").write_text("x\n");git(root,"add","x.txt");git(root,"commit","-qm","integrated");commit=git(root,"rev-parse","HEAD").stdout.strip()
  receipt={"base_commit":base,"changed_paths":["x.txt"],"integration":{"pr_number":1,"commit":commit,"method":"squash"}}
  p=root/"r.json";p.write_text(json.dumps(receipt));assert validate_receipt(p,root)["verified"] is True
  receipt["changed_paths"]=["wrong.txt"];p.write_text(json.dumps(receipt))
  try:validate_receipt(p,root)
  except ValueError as exc:assert "Git diff paths" in str(exc)
  else:raise AssertionError("tampered receipt paths must fail")
 print("Grow Doc receipt history self-test: PASS")

def main():
 a=argparse.ArgumentParser();a.add_argument("--receipts",type=pathlib.Path,default=ROOT/"contributions/receipts");a.add_argument("--self-test",action="store_true");x=a.parse_args()
 if x.self_test:self_test();return 0
 reports,errors=validate_dir(x.receipts)
 print(json.dumps({"ok":not errors,"reports":reports,"errors":errors},indent=2,sort_keys=True))
 return 0 if not errors else 2
if __name__=="__main__":raise SystemExit(main())
