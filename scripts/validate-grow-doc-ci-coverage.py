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
    "validate:model-source-identity-contract",
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
    "validate:model-vision-source-candidates",
    "validate:model-vision-admission-review",
    "validate:model-deploy-contract",
    "validate:model-improvement-planner",
    "validate:portable-rag-eval",
    "validate:model-runner",
    "validate:rag-snapshot",
    "validate:qlora-config",
    "validate:model-readme-contract",
    "validate:image-preprocessing",
    "validate:ci-validator-coverage",
}

DELEGATED_WITH_DEDICATED_WORKFLOW={
    "validate:crop-geometry":".github/workflows/validate-data-release.yml",
    "validate:data-release":".github/workflows/validate-data-release.yml",
    "validate:release-metadata":".github/workflows/validate-data-release.yml",
}

INLINE_EQUIVALENTS={
    "validate:base-vs-rag-launcher":[
        "python3 scripts/run-base-vs-rag-experiment.py --self-test",
    ],
    "validate:model-grounding":[
        "python3 scripts/enforce-supplied-claim-grounding.py --self-test",
        "python3 scripts/split-model-training-grounded.py --self-test",
        "python3 scripts/split-model-training-grounded.py --check-only",
    ],
    "validate:qlora-dependencies":[
        "python3 scripts/verify-qlora-dependency-contract.py",
    ],
    "validate:qlora-trainer":[
        "python3 scripts/train-grow-doc-qlora.py --self-test",
    ],
}

PACKAGE_EQUIVALENTS={
    "validate:external-source-registries":{
        "enforced_by":"validate:bioinformatics-contracts",
        "needles":[
            "validate-cornell-bioinformatics-registry.py",
            "validate-pubchem-chemistry-registry.py",
            "validate-plant-phenotyping-source-registry.py",
        ],
    },
    "validate:crop-ontology-ingestion":{
        "enforced_by":"validate:bioinformatics-contracts",
        "needles":["npm run validate:crop-ontology-ingestion"],
    },
    "validate:pubchem-seed-ingestion":{
        "enforced_by":"validate:bioinformatics-contracts",
        "needles":["npm run validate:pubchem-seed-ingestion"],
    },
    "validate:pubchem-collector":{
        "enforced_by":"validate:bioinformatics-contracts",
        "needles":["collect-pubchem-compound.py --self-test"],
    },
    "validate:grow-doc-receipt-history":{
        "enforced_by":"validate:grow-doc-contributions",
        "needles":["npm run validate:grow-doc-receipt-history"],
    },
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
    for name,needles in INLINE_EQUIVALENTS.items():
        if name not in scripts:
            errors.append(f"inline-equivalent script missing from package.json: {name}")
        for needle in needles:
            if needle not in ci:
                errors.append(f"primary CI missing inline equivalent for {name}: {needle}")
    for name,rule in PACKAGE_EQUIVALENTS.items():
        if name not in scripts:
            errors.append(f"package-equivalent validator missing from package.json: {name}")
            continue
        parent=rule["enforced_by"]
        parent_command=scripts.get(parent)
        if not isinstance(parent_command,str):
            errors.append(f"{name}: enforcing package script missing: {parent}")
            continue
        if f"npm run {parent}" not in ci:
            errors.append(f"{name}: enforcing package script is not in primary CI: {parent}")
        for needle in rule["needles"]:
            if needle not in parent_command:
                errors.append(f"{name}: {parent} missing equivalent command fragment: {needle}")
    validate_scripts={name for name in scripts if name.startswith("validate:")}
    classified=set(CRITICAL_MAIN_CI)|set(DELEGATED_WITH_DEDICATED_WORKFLOW)|set(INLINE_EQUIVALENTS)|set(PACKAGE_EQUIVALENTS)
    missing=sorted(validate_scripts-classified)
    stale=sorted(classified-validate_scripts)
    if missing:
        errors.append(f"unclassified validate scripts: {missing}")
    if stale:
        errors.append(f"classification references missing validate scripts: {stale}")
    if "npm run validate:ci-validator-coverage" not in ci:
        errors.append("primary CI does not enforce validator coverage audit")
    if errors:
        fail("; ".join(errors))
    return {
      "critical_main_ci":len(CRITICAL_MAIN_CI),
      "delegated":len(DELEGATED_WITH_DEDICATED_WORKFLOW),
      "inline_equivalents":len(INLINE_EQUIVALENTS),
      "package_equivalents":len(PACKAGE_EQUIVALENTS),
      "classified_total":len(CRITICAL_MAIN_CI|set(DELEGATED_WITH_DEDICATED_WORKFLOW)|set(INLINE_EQUIVALENTS)|set(PACKAGE_EQUIVALENTS)),
      "package_validate_total":len([name for name in scripts if name.startswith("validate:")]),
    }

def self_test()->None:
    result=validate()
    assert result["critical_main_ci"]>=30
    assert result["classified_total"]==result["package_validate_total"]
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
