#!/usr/bin/env python3
"""Prioritize corroboration discovery candidates by removing cross-profile boilerplate reuse.

This is a discovery-only helper. It never upgrades evidence, never edits source data, and never
makes a candidate eligible for training. Claims copied verbatim across many diagnostic profiles
are poor proposition-review candidates because they are usually study-wide methods, figure
captions, licensing notes, or other non-profile-specific context. The script preserves the raw
discovery queue and writes a separate priority queue plus an audit summary.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_PROFILES = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_DISCOVERY = ROOT / "model_tuning/generated/corroboration/discovery_queue_v1.jsonl"
DEFAULT_PRIORITY = ROOT / "model_tuning/generated/corroboration/discovery_priority_v1.jsonl"
DEFAULT_SUMMARY = ROOT / "model_tuning/generated/corroboration/discovery_noise_audit_v1.json"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def profile_frequency(profiles: list[dict]) -> dict[str, set[str]]:
    frequencies: dict[str, set[str]] = defaultdict(set)
    for profile in profiles:
        if profile.get("reviewStatus") != "reviewed":
            continue
        profile_id = profile.get("id") or ""
        for source in profile.get("sources") or []:
            for claim in source.get("supportedClaims") or []:
                key = norm(claim)
                if key:
                    frequencies[key].add(profile_id)
    return frequencies


def prioritize(profiles: list[dict], discovery: list[dict], max_profile_reuse: int) -> tuple[list[dict], dict]:
    frequencies = profile_frequency(profiles)
    priority = []
    excluded = []
    for row in discovery:
        count_a = len(frequencies.get(norm(row.get("claim_a") or ""), set()))
        count_b = len(frequencies.get(norm(row.get("claim_b") or ""), set()))
        audited = dict(row)
        audited["cross_profile_reuse"] = {"claim_a_profiles": count_a, "claim_b_profiles": count_b}
        audited["eligible_for_corroboration"] = False
        audited["eligible_for_training"] = False
        audited["auto_merge"] = False
        if count_a > max_profile_reuse or count_b > max_profile_reuse:
            audited["priority_status"] = "excluded_cross_profile_reuse"
            excluded.append(audited)
            continue
        audited["priority_status"] = "priority_human_review"
        priority.append(audited)

    priority.sort(key=lambda row: (
        -row.get("similarity", {}).get("mean_score", 0.0),
        row.get("profile_id") or "",
        norm(row.get("claim_a") or ""),
        norm(row.get("claim_b") or ""),
    ))
    summary = {
        "raw_discovery_candidates": len(discovery),
        "priority_human_review_candidates": len(priority),
        "excluded_cross_profile_reuse": len(excluded),
        "max_profile_reuse": max_profile_reuse,
        "auto_merged": 0,
        "training_promoted": 0,
    }
    return priority, summary


def self_test() -> None:
    shared = "Figure caption describing multiple unrelated nutrient deficiency panels."
    specific_a = "Older leaves developed yellow flecks followed by tan lesions."
    specific_b = "Older foliage first showed yellow specks that progressed to tan lesions."
    profiles = [
        {"id": "a", "reviewStatus": "reviewed", "sources": [{"supportedClaims": [shared, specific_a]}]},
        {"id": "b", "reviewStatus": "reviewed", "sources": [{"supportedClaims": [shared]}]},
        {"id": "c", "reviewStatus": "reviewed", "sources": [{"supportedClaims": [shared]}]},
    ]
    discovery = [
        {"profile_id": "a", "claim_a": shared, "claim_b": specific_b, "similarity": {"mean_score": 0.4}, "auto_merge": False, "eligible_for_corroboration": False, "eligible_for_training": False},
        {"profile_id": "a", "claim_a": specific_a, "claim_b": specific_b, "similarity": {"mean_score": 0.5}, "auto_merge": False, "eligible_for_corroboration": False, "eligible_for_training": False},
    ]
    priority, summary = prioritize(profiles, discovery, 2)
    assert len(priority) == 1
    assert priority[0]["claim_a"] == specific_a
    assert priority[0]["priority_status"] == "priority_human_review"
    assert priority[0]["eligible_for_training"] is False
    assert summary["excluded_cross_profile_reuse"] == 1
    assert summary["training_promoted"] == 0
    print("Corroboration discovery noise filter self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=pathlib.Path, default=DEFAULT_PROFILES)
    parser.add_argument("--discovery", type=pathlib.Path, default=DEFAULT_DISCOVERY)
    parser.add_argument("--priority-output", type=pathlib.Path, default=DEFAULT_PRIORITY)
    parser.add_argument("--summary-output", type=pathlib.Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-profile-reuse", type=int, default=2)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    profiles = load_jsonl(args.profiles)
    discovery = load_jsonl(args.discovery)
    priority, summary = prioritize(profiles, discovery, args.max_profile_reuse)
    args.priority_output.parent.mkdir(parents=True, exist_ok=True)
    args.priority_output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in priority), encoding="utf-8")
    args.summary_output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
