#!/usr/bin/env python3
"""Validate the fail-closed Grow Doc production deploy contract."""
from __future__ import annotations
import argparse,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1]
WF=ROOT/".github/workflows/deploy-dtfseeds.yml"
HELPER=ROOT/"scripts/prepare-grow-doc-deploy-dispatch.py"
REQUIRED=[
    "workflow_dispatch:",
    "commit_sha:",
    "TARGET_SHA: ${{ inputs.commit_sha }}",
    '[[ "${TARGET_SHA}" =~ ^[0-9a-f]{40}$ ]]',
    "ref: ${{ inputs.commit_sha }}",
    "fetch-depth: 0",
    "git fetch origin main --no-tags",
    'test "$(git rev-parse HEAD)" = "${TARGET_SHA}"',
    'git merge-base --is-ancestor "${TARGET_SHA}" origin/main',
    'echo "commit=${TARGET_SHA}" >> dist/deploy-version.txt',
    "DTFSEEDS_FTP_SERVER",
    "DTFSEEDS_FTP_USERNAME",
    "DTFSEEDS_FTP_PASSWORD",
    "DTFSEEDS_FTP_SERVER_DIR",
]
FORBIDDEN=[
    'echo "commit=${GITHUB_SHA}"',
    "dangerous-clean-slate: true",
]
def fail(msg):raise ValueError(msg)
def validate():
    text=WF.read_text(encoding="utf-8")
    for needle in REQUIRED:
        if needle not in text:fail(f"deploy workflow missing contract fragment: {needle}")
    for needle in FORBIDDEN:
        if needle in text:fail(f"deploy workflow contains forbidden fragment: {needle}")
    helper=HELPER.read_text(encoding="utf-8")
    for needle in ("--commit-sha","merge-base","origin/main","gh workflow run","deploy-version.txt"):
        if needle not in helper:fail(f"deploy dispatch helper missing contract fragment: {needle}")
def self_test():
    validate()
    print("Grow Doc deploy contract self-test: PASS")
def main():
    p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");a=p.parse_args()
    try:
        validate()
        if a.self_test:self_test()
        else:print("Grow Doc deploy contract: PASS")
    except (OSError,ValueError) as exc:
        print(f"Grow Doc deploy contract: FAIL: {exc}");return 2
    return 0
if __name__=="__main__":raise SystemExit(main())
