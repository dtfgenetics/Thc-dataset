#!/usr/bin/env python3
"""Fail-closed decision gate for reviewed Grow Doc base-vs-RAG reports.

The scorer's descriptive preference is intentionally not a promotion decision. This gate
adds a material-improvement requirement aligned with the existing adapter promotion
contract: >=2.0 percentage points overall and zero regressions in every critical slice.
It never authorizes adapter/model merging or deployment.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

MIN_GAIN_PP = 2.0
CRITICAL_SLICES = {
    "citation_accuracy", "diagnostic", "education", "factuality", "grounded_qa",
    "hallucination", "regression", "science",
}


def decision(report: dict) -> dict:
    if report.get("schema_version") != "grow-doc-base-vs-rag-reviewed-score-v1":
        return {"eligible": False, "reason": "unexpected or missing reviewed score schema"}
    comparison = report.get("comparison") or {}
    if comparison.get("review_complete") is not True:
        return {"eligible": False, "reason": "human-reviewed semantic comparison is incomplete"}
    gain = comparison.get("aggregate_gain_pp")
    if not isinstance(gain, (int, float)):
        return {"eligible": False, "reason": "aggregate gain is missing"}

    base_slices = (report.get("base") or {}).get("slices") or {}
    rag_slices = (report.get("rag") or {}).get("slices") or {}
    missing = sorted(s for s in CRITICAL_SLICES if s not in base_slices or s not in rag_slices)
    regressions = []
    for name in sorted(CRITICAL_SLICES - set(missing)):
        base = (base_slices.get(name) or {}).get("aggregate")
        rag = (rag_slices.get(name) or {}).get("aggregate")
        if not isinstance(base, (int, float)) or not isinstance(rag, (int, float)):
            missing.append(name)
        elif rag < base:
            regressions.append({"slice": name, "base": base, "rag": rag, "delta_pp": round((rag-base)*100, 2)})

    eligible = gain >= MIN_GAIN_PP and not regressions and not missing
    reason = "material gain with zero critical-slice regressions" if eligible else "decision gate not met"
    return {
        "eligible": eligible,
        "reason": reason,
        "aggregate_gain_pp": gain,
        "minimum_gain_pp": MIN_GAIN_PP,
        "critical_regressions": regressions,
        "missing_critical_slices": sorted(set(missing)),
        "merge_or_deploy_authorized": False,
    }


def self_test() -> None:
    slices = {s: {"aggregate": 0.70} for s in CRITICAL_SLICES}
    base = {"slices": json.loads(json.dumps(slices))}
    rag = {"slices": json.loads(json.dumps(slices))}
    fixture = {
        "schema_version": "grow-doc-base-vs-rag-reviewed-score-v1",
        "comparison": {"review_complete": True, "aggregate_gain_pp": 2.0},
        "base": base, "rag": rag,
    }
    assert decision(fixture)["eligible"] is True
    fixture["comparison"]["aggregate_gain_pp"] = 0.01
    assert decision(fixture)["eligible"] is False
    fixture["comparison"]["aggregate_gain_pp"] = 5.0
    fixture["rag"]["slices"]["diagnostic"]["aggregate"] = 0.69
    out = decision(fixture)
    assert out["eligible"] is False and out["critical_regressions"][0]["slice"] == "diagnostic"
    fixture["rag"]["slices"]["diagnostic"]["aggregate"] = 0.70
    del fixture["rag"]["slices"]["citation_accuracy"]
    assert decision(fixture)["eligible"] is False
    print("base-vs-RAG decision gate self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report")
    parser.add_argument("--out")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    if not args.report:
        parser.error("--report is required")
    try:
        report = json.loads(pathlib.Path(args.report).read_text(encoding="utf-8"))
        result = decision(report)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"base-vs-RAG decision gate: FAIL: {exc}", file=sys.stderr); return 2
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
