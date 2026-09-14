#!/usr/bin/env python3
"""Fail material Grow Doc training-supervision concentration regressions.

This validator consumes the existing strong-evidence concentration audit and a small,
reviewed policy file. Limits are derived from the frozen measured baseline and are
intentionally loose enough to catch large concentration regressions rather than force
artificial balancing. It never edits, drops, downsamples, or reweights supervision.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts/audit-training-supervision-concentration.py"
DEFAULT_POLICY = ROOT / "model_tuning/training-supervision-concentration-policy.json"
POLICY_SCHEMA = "grow-doc-training-supervision-concentration-policy-v1"
METRICS = (
    "top_source_example_share",
    "top_profile_example_share",
    "top_task_example_share",
)


def load_module(path: pathlib.Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require_share(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    share = float(value)
    if not 0.0 <= share <= 1.0:
        raise ValueError(f"{label} must be within [0, 1], got {share}")
    return share


def _require_positive(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if number <= 0.0:
        raise ValueError(f"{label} must be > 0, got {number}")
    return number


def validate_policy(data: dict) -> dict:
    if data.get("schema_version") != POLICY_SCHEMA:
        raise ValueError(f"unsupported concentration policy schema: {data.get('schema_version')}")

    policy = data.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("concentration policy.policy must be an object")
    if policy.get("rag_first") is not True:
        raise ValueError("concentration policy must preserve rag_first=true")
    if policy.get("automatic_rebalancing") is not False:
        raise ValueError("concentration policy must preserve automatic_rebalancing=false")
    if policy.get("delete_or_downsample_to_pass") is not False:
        raise ValueError("concentration policy must forbid delete_or_downsample_to_pass")
    if policy.get("require_frozen_baseline") is not True:
        raise ValueError("concentration policy must require a frozen baseline")

    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("concentration policy.metrics must be an object")
    if set(metrics) != set(METRICS):
        raise ValueError(f"concentration policy metrics must be exactly {sorted(METRICS)}")

    for metric in METRICS:
        rule = metrics.get(metric)
        if not isinstance(rule, dict):
            raise ValueError(f"concentration policy rule for {metric} must be an object")
        absolute_margin = _require_share(rule.get("absolute_margin"), f"{metric}.absolute_margin")
        baseline_multiplier = _require_positive(rule.get("baseline_multiplier"), f"{metric}.baseline_multiplier")
        if baseline_multiplier < 1.0:
            raise ValueError(f"{metric}.baseline_multiplier must be >= 1.0")
        if absolute_margin == 0.0 and baseline_multiplier == 1.0:
            raise ValueError(f"{metric} rule must allow some measured drift above baseline")
    return data


def load_policy(path: pathlib.Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("concentration policy must be a JSON object")
    return validate_policy(data)


def threshold_for(baseline_share: float, rule: dict) -> float:
    absolute = baseline_share + float(rule["absolute_margin"])
    relative = baseline_share * float(rule["baseline_multiplier"])
    return min(1.0, max(absolute, relative))


def evaluate(report: dict, baseline: dict, policy: dict) -> dict:
    failures: list[dict] = []
    metrics_report: dict[str, dict] = {}
    for metric in METRICS:
        current = _require_share(report.get(metric), f"report.{metric}")
        previous = _require_share(baseline.get(metric), f"baseline.{metric}")
        rule = policy["metrics"][metric]
        threshold = threshold_for(previous, rule)
        passed = current <= threshold + 1e-12
        metrics_report[metric] = {
            "current": round(current, 6),
            "baseline": round(previous, 6),
            "allowed_max": round(threshold, 6),
            "passed": passed,
        }
        if not passed:
            failures.append(
                {
                    "metric": metric,
                    "current": round(current, 6),
                    "allowed_max": round(threshold, 6),
                    "baseline": round(previous, 6),
                }
            )

    return {
        "schema_version": "grow-doc-training-supervision-concentration-validation-v1",
        "passed": not failures,
        "candidate_examples": report.get("candidate_examples"),
        "baseline_commit": baseline.get("baseline_commit"),
        "metrics": metrics_report,
        "failures": failures,
        "policy": {
            "rag_first": True,
            "automatic_rebalancing": False,
            "delete_or_downsample_to_pass": False,
            "interpretation": "large-regression safety gate, not a balancing target",
        },
    }


def self_test() -> None:
    policy = {
        "schema_version": POLICY_SCHEMA,
        "policy": {
            "rag_first": True,
            "automatic_rebalancing": False,
            "delete_or_downsample_to_pass": False,
            "require_frozen_baseline": True,
        },
        "metrics": {
            "top_source_example_share": {"absolute_margin": 0.03, "baseline_multiplier": 1.5},
            "top_profile_example_share": {"absolute_margin": 0.03, "baseline_multiplier": 2.0},
            "top_task_example_share": {"absolute_margin": 0.08, "baseline_multiplier": 1.2},
        },
    }
    validate_policy(policy)
    baseline = {
        "baseline_commit": "a" * 40,
        "top_source_example_share": 0.066265,
        "top_profile_example_share": 0.033133,
        "top_task_example_share": 0.466867,
    }
    at_baseline = {"candidate_examples": 332, **{metric: baseline[metric] for metric in METRICS}}
    result = evaluate(at_baseline, baseline, policy)
    assert result["passed"] is True
    assert result["metrics"]["top_source_example_share"]["allowed_max"] == 0.099397
    assert result["metrics"]["top_profile_example_share"]["allowed_max"] == 0.066266
    assert result["metrics"]["top_task_example_share"]["allowed_max"] == 0.56024

    source_spike = dict(at_baseline)
    source_spike["top_source_example_share"] = 0.11
    result = evaluate(source_spike, baseline, policy)
    assert result["passed"] is False
    assert result["failures"][0]["metric"] == "top_source_example_share"

    task_spike = dict(at_baseline)
    task_spike["top_task_example_share"] = 0.57
    result = evaluate(task_spike, baseline, policy)
    assert result["passed"] is False

    bad = json.loads(json.dumps(policy))
    bad["policy"]["rag_first"] = False
    try:
        validate_policy(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("policy with rag_first=false must be rejected")

    bad = json.loads(json.dumps(policy))
    bad["policy"]["automatic_rebalancing"] = True
    try:
        validate_policy(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("automatic rebalancing must be rejected")

    print("training supervision concentration validation self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Grow Doc training-supervision concentration against frozen baseline-relative guardrails.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--policy", type=pathlib.Path, default=DEFAULT_POLICY)
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        audit = load_module(AUDIT_SCRIPT, "grow_doc_supervision_concentration_audit")
        policy = load_policy(args.policy)
        baseline = audit.load_baseline(audit.DEFAULT_BASELINE)
        if baseline is None:
            raise ValueError("frozen concentration baseline is required")
        report = audit.run(audit.DEFAULT_BASELINE)
        result = evaluate(report, baseline, policy)
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["passed"]:
        print("training supervision concentration validation: FAIL")
        return 1
    print("training supervision concentration validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
