#!/usr/bin/env python3
"""Turn Grow Doc evaluation evidence into a prioritized improvement backlog.

This is intentionally not a model promoter. It converts reviewed benchmark results into
specific RAG, SFT, diagnostics, or evaluation actions while preserving the rule that
changing factual knowledge belongs in retrieval by default.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

PROTECTED = (
    "factuality", "diagnostic", "hallucination", "citation_accuracy",
    "science", "education", "grounded_qa", "regression",
)

ACTION_MAP = {
    "factuality": ("rag", "Improve retrieval coverage/ranking and source freshness before adding factual SFT."),
    "citation_accuracy": ("rag", "Improve source-ID propagation, retrieval provenance, and citation rendering."),
    "science": ("rag", "Add or repair verified scientific claims in the retrieval corpus; keep claim limits explicit."),
    "diagnostic": ("sft_behavior", "Add evidence-ranked differential/abstention examples; do not encode unsupported diagnoses."),
    "hallucination": ("sft_behavior", "Add supplied-evidence abstention and forbidden-overclaim examples."),
    "education": ("sft_behavior", "Add concise explanation/scaffolding examples grounded in supplied claims."),
    "grounded_qa": ("rag+sft_behavior", "Inspect retrieval misses first, then add evidence-use behavior examples if retrieval is adequate."),
    "regression": ("eval+targeted_fix", "Trace the failing behavior to retrieval or SFT and add a targeted regression case before changing weights."),
}

def load_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value

def slice_scores(summary: dict[str, Any] | None) -> dict[str, float]:
    if not summary:
        return {}
    out: dict[str, float] = {}
    for name, row in (summary.get("slices") or {}).items():
        value = (row or {}).get("aggregate") if isinstance(row, dict) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[name] = float(value)
    return out

def plan(base_rag: dict[str, Any] | None, adapter: dict[str, Any] | None) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    best_scores: dict[str, float] = {}

    if base_rag:
        base = slice_scores(base_rag.get("base"))
        rag = slice_scores(base_rag.get("rag"))
        for name in PROTECTED:
            if name in base and name in rag:
                delta = rag[name] - base[name]
                best_scores[name] = max(base[name], rag[name])
                observations.append({
                    "slice": name, "comparison": "base_vs_rag",
                    "base": base[name], "candidate": rag[name],
                    "delta_pp": round(delta * 100, 2),
                    "retrieval_helped": delta > 0,
                })

    if adapter:
        baseline = slice_scores(adapter.get("baseline"))
        candidate = slice_scores(adapter.get("candidate"))
        for name in PROTECTED:
            if name in baseline and name in candidate:
                delta = candidate[name] - baseline[name]
                best_scores[name] = max(best_scores.get(name, 0.0), baseline[name], candidate[name])
                observations.append({
                    "slice": name, "comparison": "adapter_vs_baseline",
                    "base": baseline[name], "candidate": candidate[name],
                    "delta_pp": round(delta * 100, 2),
                    "adapter_helped": delta > 0,
                })

    priorities = []
    for name in PROTECTED:
        score = best_scores.get(name)
        lane, action = ACTION_MAP[name]
        # Missing measurements outrank measured tuning work: we cannot improve what is not scored.
        if score is None:
            severity = 1.0
            reason = "missing protected-slice measurement"
        else:
            severity = round(1.0 - score, 4)
            reason = f"best reviewed aggregate={score:.3f}"
        priorities.append({
            "slice": name,
            "priority": severity,
            "lane": lane,
            "reason": reason,
            "next_action": action,
        })

    priorities.sort(key=lambda x: (-x["priority"], PROTECTED.index(x["slice"])))
    measured = len(best_scores)
    return {
        "schema_version": "grow-doc-improvement-plan-v1",
        "promotion_authorized": False,
        "protected_slices_measured": measured,
        "protected_slices_total": len(PROTECTED),
        "ready_for_targeted_improvement": measured == len(PROTECTED),
        "priorities": priorities,
        "observations": observations,
        "policy": {
            "facts": "Prefer RAG for changing/source-dependent factual knowledge.",
            "weights": "Use SFT/LoRA for evidence-use behavior, diagnostic procedure, abstention, and educational structure.",
            "promotion": "Only existing reviewed promotion gates may authorize candidate promotion.",
        },
    }

def self_test() -> None:
    slices = {name: {"aggregate": 0.70} for name in PROTECTED}
    rag = {name: {"aggregate": 0.75} for name in PROTECTED}
    rag["diagnostic"]["aggregate"] = 0.60
    report = {"base": {"slices": slices}, "rag": {"slices": rag}}
    result = plan(report, None)
    assert result["ready_for_targeted_improvement"] is True
    diagnostic = next(x for x in result["priorities"] if x["slice"] == "diagnostic")
    assert diagnostic["lane"] == "sft_behavior"
    assert diagnostic["priority"] == 0.3
    obs = next(x for x in result["observations"] if x["slice"] == "diagnostic")
    assert obs["retrieval_helped"] is False

    missing = plan(None, None)
    assert missing["ready_for_targeted_improvement"] is False
    assert missing["priorities"][0]["reason"] == "missing protected-slice measurement"
    print("Grow Doc improvement planner self-test: PASS")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-rag-report")
    parser.add_argument("--adapter-report")
    parser.add_argument("--out")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        result = plan(load_json(args.base_rag_report), load_json(args.adapter_report))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Grow Doc improvement planner: FAIL: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
