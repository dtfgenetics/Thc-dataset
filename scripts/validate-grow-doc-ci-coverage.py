#!/usr/bin/env python3
"""Ensure critical Grow Doc validators are enforced by the primary CI workflow."""
from __future__ import annotations
import argparse,json,pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
PKG=ROOT/"package.json"
CI=ROOT/".github/workflows/ci.yml"

CRITICAL_MAIN_CI={
    "validate:sources",
    "validate:acquisition",
    "validate:transfer",
    "validate:diagnostic-profiles",
    "validate:grow-doc-contributions",
    "validate:grow-doc-task-registry",
    "validate:grow-doc-agent-state",
    "validate:grow-doc-claims",
    "validate:source-intake",
    "validate:claim-relationships",
    "validate:bioinformatics-contracts",
    "validate:tool-data-bundle-production",
    "validate:model-eval",
    "validate:model-base-candidates",
    "validate:model-eval-candidates",
    "validate:model-eval-candidate-leakage",
    "validate:model-eval-gap-research",
    "validate:model-eval-coverage",
    "validate:diagnostic-abstention-dev",
    "validate:model-corpus-quality",
    "validate:training-supervision-concentration",
    "validate:model-source-evidence-quality",
    "validate:model-example-evidence-tiers",
    "validate:model-semantic-leakage",
    "validate:model-corpus",
    "validate:grounded-qa",
    "validate:reviewed-claim-grounded-qa",
    "validate:model-split",
    "validate:training-dataset-manifest",
    "validate:model-scorer",
    "validate:model-run-manifest",
    "validate:model-experiment-registry",
    "validate:model-checkpoint-registry",
    "validate:model-project-completion",
    "validate:model-external-blockers",
    "validate:model-improvement-planner",
    "validate:portable-rag-eval",
    "validate:model-runner",
    "validate:rag-snapshot",
    "validate:qlora-config",
    "validate:model-readme-contract",
    "validate:image-preprocessing",
}

DELEGATED_WITH_DEDICATED_WORKFLOW={
    "validate:crop-geometry":".github/workflows/validate-data-release.yml",
    "validate:release-metadata":".github/workflows/validate-data-release.yml",
}

INLINE_EQUIVALENTS={
    "validate:base-vs-rag-launcher":"python3 scripts/run-base-vs-rag-experiment.py --self-test",
    "validate:qlora-dependencies":"python3 scripts/verify-qlora-dependency-contract.py",
    "validate:qlora-trainer":"python3 scripts/train-grow-doc-qlora.py --self-test",
}

def fail(msg:str)->None: raise ValueError(msg)

def validate()->dict:
    pkg=json.loads(PKG.read_text(encoding="utf-8"))
    scripts=pkg.get("scripts") or {}
    ci=CI.read_text(encoding="utf-8")
    errors=[]
    for name in sorted(CRITICAL_MAIN_CI):
        if name not in scripts:
            errors.append(f"critical script missing from package.json: {name}")
        elif f"npm run {name}" not in ci:
            errors.append(f"critical validator not enforced in primary CI: {name}")
    for name,path in DELEGATED_WITH_DEDICATED_WORKFLOW.items():
        if name not in scripts:
            errors.append(f"delegated validator missing from package.json: {name}")
            continue
        wf=ROOT/path
        if not wf.is_file():
            errors.append(f"delegated workflow missing for {name}: {path}")
            continue
        text=wf.read_text(encoding="utf-8")
        if f"npm run {name}" not in text:
            errors.append(f"delegated workflow does not enforce {name}: {path}")
    for name,needle in INLINE_EQUIVALENTS.items():
        if name not in scripts:
            errors.append(f"inline-equivalent script missing from package.json: {name}")
        if needle not in ci:
            errors.append(f"primary CI missing inline equivalent for {name}: {needle}")
    if "npm run validate:ci-validator-coverage" not in ci:
        errors.append("primary CI does not enforce validator coverage audit")
    if errors:
        fail("; ".join(errors))
    return {
      "critical_main_ci":len(CRITICAL_MAIN_CI),
      "delegated":len(DELEGATED_WITH_DEDICATED_WORKFLOW),
      "inline_equivalents":len(INLINE_EQUIVALENTS),
    }

def self_test()->None:
    result=validate()
    assert result["critical_main_ci"]>=30
    print("Grow Doc CI validator coverage self-test: PASS")

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");a=p.parse_args()
    try:
        result=validate()
        if a.self_test:self_test()
        else:print(json.dumps({"ok":True,**result},sort_keys=True))
    except (OSError,json.JSONDecodeError,ValueError) as exc:
        print(f"Grow Doc CI validator coverage: FAIL: {exc}")
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
