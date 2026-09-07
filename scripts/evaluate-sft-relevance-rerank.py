#!/usr/bin/env python3
"""Evaluate Grow Doc SFT evidence ranking before changing frozen training artifacts.

Dry-run only. It compares original source order, the prior relevance-only policy, and the actual
production ranker. This prevents the evaluation lane from silently testing a duplicated/obsolete
ranking implementation. Global RAG membership and provenance are untouched.
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
RANKER_PATH = ROOT / "scripts/sft_evidence_ranking.py"


def load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def claim_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def candidate_rows(profile: dict, heldout: set[str], audit) -> list[dict]:
    rows = []
    seen = set()
    for source_index, source in enumerate(profile.get("sources") or []):
        sid = audit.source_id(source)
        if sid in heldout:
            continue
        for claim_index, claim in enumerate(source.get("supportedClaims") or []):
            key = claim_key(claim)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append({
                "claim": claim,
                "source_id": sid,
                "source": source,
                "source_index": source_index,
                "claim_index": claim_index,
            })
    return rows


def relevance_only_rank(profile: dict, rows: list[dict], owners_by_anchor: dict[str, set[str]], audit) -> list[dict]:
    pid = profile.get("id")
    target = audit.profile_anchors(profile)
    ranked = []
    for index, row in enumerate(rows):
        ctokens = audit.tokens(row.get("claim") or "")
        target_hits = target & ctokens
        foreign_hits = {
            token for token in ctokens
            if token in owners_by_anchor
            and token not in target
            and any(owner != pid for owner in owners_by_anchor[token])
        }
        tier = 0 if target_hits else (2 if foreign_hits else 1)
        ranked.append((tier, -len(target_hits), len(foreign_hits), index, row))
    ranked.sort(key=lambda item: item[:4])
    return [item[-1] for item in ranked]


def rebuild_profiles(profiles: list[dict], heldout: set[str], audit, ranker, mode: str) -> list[dict]:
    reviewed = [p for p in profiles if p.get("reviewStatus") == "reviewed" and p.get("id")]
    owners_by_anchor: dict[str, set[str]] = defaultdict(set)
    for profile in reviewed:
        for anchor in audit.profile_anchors(profile):
            owners_by_anchor[anchor].add(profile["id"])
    production_owners = ranker.build_anchor_owners(profiles)

    out = []
    for profile in profiles:
        clone = json.loads(json.dumps(profile))
        if clone.get("reviewStatus") != "reviewed" or not clone.get("id"):
            out.append(clone)
            continue
        rows = candidate_rows(clone, heldout, audit)
        if mode == "source_order":
            ordered = rows
        elif mode == "relevance_only":
            ordered = relevance_only_rank(clone, rows, owners_by_anchor, audit)
        elif mode == "production":
            ordered = ranker.rank_sft_evidence(clone, rows, production_owners)
        else:
            raise ValueError(f"unknown ranking mode: {mode}")

        ranked_sources = []
        for row in ordered:
            source = row["source"]
            ranked_sources.append({
                **{k: v for k, v in source.items() if k != "supportedClaims"},
                "supportedClaims": [row["claim"]],
            })
        clone["sources"] = ranked_sources
        out.append(clone)
    return out


def provenance_metrics(profiles: list[dict], heldout: set[str], audit, top_n: int = 5) -> dict:
    doi_slots = 0
    url_slots = 0
    total_slots = 0
    profiles_with_context = 0
    profiles_with_doi = 0
    for profile in profiles:
        if profile.get("reviewStatus") != "reviewed" or not profile.get("id"):
            continue
        rows = candidate_rows(profile, heldout, audit)[:top_n]
        if not rows:
            continue
        profiles_with_context += 1
        has_doi = False
        for row in rows:
            total_slots += 1
            sid = str(row.get("source_id") or "").lower()
            if sid.startswith("doi:"):
                doi_slots += 1
                has_doi = True
            elif sid.startswith("url:"):
                url_slots += 1
        if has_doi:
            profiles_with_doi += 1
    return {
        "top_n": top_n,
        "context_slots": total_slots,
        "doi_slots": doi_slots,
        "url_slots": url_slots,
        "doi_slot_rate": round(doi_slots / total_slots, 6) if total_slots else 0.0,
        "profiles_with_context": profiles_with_context,
        "profiles_with_doi_in_top_context": profiles_with_doi,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    ap.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    ap.add_argument("--require-improvement", action="store_true")
    args = ap.parse_args()
    try:
        audit = load_module(AUDIT_PATH, "sft_relevance_audit")
        ranker = load_module(RANKER_PATH, "sft_evidence_ranking")
        profiles = audit.load_jsonl(args.input)
        heldout = audit.heldout_source_ids(args.eval)
        source_order = rebuild_profiles(profiles, heldout, audit, ranker, "source_order")
        relevance_only = rebuild_profiles(profiles, heldout, audit, ranker, "relevance_only")
        production = rebuild_profiles(profiles, heldout, audit, ranker, "production")
        before = audit.audit(source_order, heldout)
        relevance = audit.audit(relevance_only, heldout)
        after = audit.audit(production, heldout)
        source_provenance = provenance_metrics(source_order, heldout, audit)
        relevance_provenance = provenance_metrics(relevance_only, heldout, audit)
        production_provenance = provenance_metrics(production, heldout, audit)
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    report = {
        "mode": "dry_run_only_no_training_artifacts_modified",
        "source_order": before,
        "relevance_only": relevance,
        "production": after,
        "foreign_only_slots_reduced_vs_source_order": before["foreign_only_context_slots"] - after["foreign_only_context_slots"],
        "foreign_only_rate_delta_vs_source_order": round(after["foreign_only_rate"] - before["foreign_only_rate"], 6),
        "provenance": {
            "source_order": source_provenance,
            "relevance_only": relevance_provenance,
            "production": production_provenance,
            "doi_slots_delta_vs_relevance_only": production_provenance["doi_slots"] - relevance_provenance["doi_slots"],
        },
        "policy": "target-explicit first; neutral target-compatible second; explicit foreign-target last; within equal relevance, DOI-backed scientific provenance before URL-only support; held-out sources excluded",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_improvement:
        if after["foreign_only_context_slots"] >= before["foreign_only_context_slots"]:
            print("production ranker did not reduce foreign-only SFT context slots", file=sys.stderr)
            return 1
        if production_provenance["doi_slots"] < relevance_provenance["doi_slots"]:
            print("production ranker regressed DOI-backed top-context coverage", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
