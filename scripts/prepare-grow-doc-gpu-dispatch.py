#!/usr/bin/env python3
"""Prepare a safe manual dispatch command for the Grow Doc GPU benchmark."""
from __future__ import annotations
import argparse, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHA40 = re.compile(r"^[0-9a-f]{40}$")

def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

def validate_sha(value: str) -> str:
    if not SHA40.fullmatch(value):
        raise ValueError("commit SHA must be exact lowercase 40-character Git SHA")
    return value

def main() -> int:
    p = argparse.ArgumentParser(description="Prepare protected Grow Doc GPU workflow dispatch.")
    p.add_argument("--commit-sha", required=True)
    p.add_argument("--run", choices=["preflight","benchmark"], default="preflight")
    p.add_argument("--workflow", default="model-base-vs-rag-gpu.yml")
    a = p.parse_args()
    try:
        sha = validate_sha(a.commit_sha)
        subprocess.run(["git","fetch","origin","main","--no-tags"], cwd=ROOT, check=True)
        resolved = git("rev-parse", f"{sha}^{{commit}}")
        if resolved != sha:
            raise ValueError("requested SHA does not resolve exactly")
        ancestor = subprocess.run(["git","merge-base","--is-ancestor",sha,"origin/main"], cwd=ROOT)
        if ancestor.returncode != 0:
            raise ValueError("requested SHA is not reachable from origin/main")
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    preflight = "true" if a.run == "preflight" else "false"
    print("Validated immutable main commit:", sha)
    print("Manual dispatch command:")
    print(f"gh workflow run {a.workflow} --ref main -f commit_sha={sha} -f preflight_only={preflight}")
    print("After dispatch, verify the queued job targets labels: self-hosted, linux, x64, growdoc-gpu.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
