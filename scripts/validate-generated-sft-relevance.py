#!/usr/bin/env python3
"""Validate target relevance in the SFT evidence emitted by the real corpus builder."""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts/build-model-corpus.py"
AUDIT_PATH = ROOT / "scripts/audit-sft-profile-relevance.py"
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
EVIDENCE_RE = re.compile(r"^\[([^\]]+)\]\s+(.+)$")


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence_rows(item: dict) -> list[dict]:
    user = next((m.get("content", "") for m in item.get("messages", []) if m.get("role") == "user"), "")
    rows = []
    for line in user.splitlines():
        match = EVIDENCE_RE.match(line.strip())
        if match:
            rows.append({"source_id": match.group(1), "claim": match.group(2)})
    return rows


def validate(input_path: pathlib.Path, eval_path: pathlib.Path) -> dict:
    builder = load_module("grow_doc_corpus_builder", BUILDER_PATH)
    audit = load_module("grow_doc_sft_audit", AUDIT_PATH)
    profiles = audit.load_jsonl(input_path)
    by_id = {p.get("id"): p for p in profiles if p.get("id")}
    anchors_by_profile = {pid: audit.profile_anchors(p) for pid, p in by_id.items() if p.get("reviewStatus") == "reviewed"}
    owners = {}
    for pid, anchors in anchors_by_profile.items():
        for anchor in anchors:
            owners.setdefault(anchor, set()).add(pid)

    _, sft, _, stats = builder.build(input_path, eval_path)
    foreign = []
    slots = 0
    seen_profile = set()
    for item in sft:
        pid = item.get("profile_id")
        # All three task variants share the same evidence window; audit it once per profile.
        if not pid or pid in seen_profile:
            continue
        seen_profile.add(pid)
        target = anchors_by_profile.get(pid, set())
        for position, row in enumerate(evidence_rows(item), 1):
            slots += 1
            ctokens = audit.tokens(row["claim"])
            target_hits = target & ctokens
            foreign_hits = sorted(
                token for token in ctokens
                if token in owners and token not in target and any(owner != pid for owner in owners[token])
            )
            if foreign_hits and not target_hits:
                foreign.append({
                    "profile_id": pid,
                    "position": position,
                    "source_id": row["source_id"],
                    "foreign_anchors": foreign_hits,
                    "claim": row["claim"],
                })
    by_profile = Counter(row["profile_id"] for row in foreign)
    return {
        "sft_examples": stats["sft_examples"],
        "profiles_audited": len(seen_profile),
        "evidence_slots_audited": slots,
        "foreign_only_context_slots": len(foreign),
        "foreign_only_rate": round(len(foreign) / slots, 6) if slots else 0.0,
        "profiles_with_foreign_only_context": len(by_profile),
        "top_profiles": by_profile.most_common(12),
        "examples": foreign[:20],
    }


def self_test() -> None:
    builder = load_module("grow_doc_corpus_builder_selftest", BUILDER_PATH)
    ranking = builder.rank_sft_evidence
    owners = {"calcium": {"ca"}, "magnesium": {"mg"}}
    profile = {"id": "ca", "name": "Calcium deficiency", "slug": "calcium-deficiency"}
    rows = [
        {"claim": "Magnesium deficiency affects older leaves.", "source_id": "foreign"},
        {"claim": "Visual symptoms can overlap between nutrient disorders.", "source_id": "neutral"},
        {"claim": "Calcium deficiency affects developing tissue.", "source_id": "target"},
    ]
    # Use the builder's real helper with a realistic owner map from its own tokenization module.
    owners = builder.build_anchor_owners([
        {**profile, "reviewStatus": "reviewed"},
        {"id": "mg", "name": "Magnesium deficiency", "slug": "magnesium-deficiency", "reviewStatus": "reviewed"},
    ])
    assert [r["source_id"] for r in ranking(profile, rows, owners)] == ["target", "neutral", "foreign"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    ap.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    ap.add_argument("--max-rate", type=float, default=0.02)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        print("generated SFT relevance self-test passed")
        return 0
    try:
        report = validate(args.input, args.eval)
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    import json
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["foreign_only_rate"] > args.max_rate:
        print(
            f"generated SFT foreign-only rate {report['foreign_only_rate']:.6f} exceeds {args.max_rate:.6f}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
