#!/usr/bin/env python3
"""Evaluate a conservative profile-to-claim reranker before changing frozen SFT artifacts.

This script is intentionally dry-run only. It measures whether profile-specific SFT contexts
would improve if candidate claims were ranked by target relevance rather than source order.
Global RAG membership and provenance are untouched.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
AUDIT_PATH = ROOT / "scripts/audit-sft-profile-relevance.py"


def load_audit_module():
    spec = importlib.util.spec_from_file_location("sft_relevance_audit", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {AUDIT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def claim_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def rank_profiles(profiles: list[dict], heldout: set[str], audit) -> list[dict]:
    reviewed = [p for p in profiles if p.get("reviewStatus") == "reviewed" and p.get("id")]
    anchors_by_profile = {p["id"]: audit.profile_anchors(p) for p in reviewed}
    owners_by_anchor: dict[str, set[str]] = defaultdict(set)
    for pid, anchors in anchors_by_profile.items():
        for anchor in anchors:
            owners_by_anchor[anchor].add(pid)

    out = []
    for profile in profiles:
        clone = json.loads(json.dumps(profile))
        pid = clone.get("id")
        if clone.get("reviewStatus") != "reviewed" or not pid:
            out.append(clone)
            continue
        target = anchors_by_profile.get(pid, set())
        candidates = []
        source_meta = []
        seen = set()
        for source_index, source in enumerate(clone.get("sources") or []):
            sid = audit.source_id(source)
            if sid in heldout:
                continue
            source_meta.append((source_index, source, sid))
            for claim_index, claim in enumerate(source.get("supportedClaims") or []):
                key = claim_key(claim)
                if not key or key in seen:
                    continue
                seen.add(key)
                ctokens = audit.tokens(claim)
                target_hits = len(target & ctokens)
                foreign_hits = {
                    token for token in ctokens
                    if token in owners_by_anchor
                    and token not in target
                    and any(owner != pid for owner in owners_by_anchor[token])
                }
                # Target-explicit claims first; neutral claims next; foreign-only claims last.
                tier = 0 if target_hits else (2 if foreign_hits else 1)
                candidates.append((tier, -target_hits, len(foreign_hits), source_index, claim_index, claim, sid))
        candidates.sort()

        # Rebuild only an audit clone: a synthetic source sequence preserves source IDs while
        # exposing the ranked claim order to the existing independent relevance audit.
        ranked_sources = []
        source_lookup = {audit.source_id(s): s for s in clone.get("sources") or []}
        for _, _, _, _, _, claim, sid in candidates:
            source = source_lookup[sid]
            ranked_sources.append({
                **{k: v for k, v in source.items() if k != "supportedClaims"},
                "supportedClaims": [claim],
            })
        clone["sources"] = ranked_sources
        out.append(clone)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    ap.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    ap.add_argument("--require-improvement", action="store_true")
    args = ap.parse_args()
    try:
        audit = load_audit_module()
        profiles = audit.load_jsonl(args.input)
        heldout = audit.heldout_source_ids(args.eval)
        before = audit.audit(profiles, heldout)
        ranked = rank_profiles(profiles, heldout, audit)
        after = audit.audit(ranked, heldout)
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    report = {
        "mode": "dry_run_only_no_training_artifacts_modified",
        "baseline": before,
        "reranked": after,
        "foreign_only_slots_reduced": before["foreign_only_context_slots"] - after["foreign_only_context_slots"],
        "foreign_only_rate_delta": round(after["foreign_only_rate"] - before["foreign_only_rate"], 6),
        "policy": "target-explicit claims first; neutral target-compatible claims second; explicit foreign-target claims last; held-out sources remain excluded from SFT evaluation",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_improvement and after["foreign_only_context_slots"] >= before["foreign_only_context_slots"]:
        print("reranker did not reduce foreign-only SFT context slots", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
