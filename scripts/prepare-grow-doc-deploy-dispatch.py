#!/usr/bin/env python3
"""Prepare a safe manual production deployment dispatch for Grow Doc."""
from __future__ import annotations
import argparse,pathlib,re,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
SHA40=re.compile(r"^[0-9a-f]{40}$")
def git(*args:str)->str:
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()
def main()->int:
    p=argparse.ArgumentParser(description="Prepare exact-main Grow Doc production deploy dispatch.")
    p.add_argument("--commit-sha",required=True)
    p.add_argument("--workflow",default="deploy-dtfseeds.yml")
    a=p.parse_args()
    sha=a.commit_sha
    if not SHA40.fullmatch(sha):
        print("ERROR: commit SHA must be exact lowercase 40-character Git SHA",file=sys.stderr);return 2
    try:
        subprocess.run(["git","fetch","origin","main","--no-tags"],cwd=ROOT,check=True)
        if git("rev-parse",f"{sha}^{{commit}}")!=sha:
            raise ValueError("requested SHA does not resolve exactly")
        if subprocess.run(["git","merge-base","--is-ancestor",sha,"origin/main"],cwd=ROOT).returncode!=0:
            raise ValueError("requested SHA is not reachable from origin/main")
    except (subprocess.CalledProcessError,ValueError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr);return 2
    print("Validated immutable main commit:",sha)
    print("Manual dispatch command:")
    print(f"gh workflow run {a.workflow} --ref main -f commit_sha={sha}")
    print("After completion, verify /thc-grow-doc/deploy-version.txt reports this exact commit.")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
