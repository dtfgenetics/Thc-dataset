#!/usr/bin/env python3
"""Audit profile-specific SFT evidence for cross-profile claim contamination.

The global RAG corpus should retain reviewed, provenance-backed claims even when a broad
source discusses several disorders. Profile-specific SFT is different: its small supplied
context should not be dominated by claims that name another diagnostic target while never
naming the target being taught.

This audit mirrors the current corpus builder's source ordering and held-out-source exclusion,
then examines the first five claims that would enter each profile's SFT context. It is
conservative and diagnostic-only: it does not delete retrieval evidence or rewrite labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"

GENERIC = {
    "abiotic", "bacterial", "cannabis", "cultivation", "deficiency", "disease",
    "disorder", "fungal", "hemp", "leaf", "leaves", "nutrient", "pathogen",
    "plant", "plants", "spot", "stress", "sativa", "symptom", "symptoms",
    "toxicity", "viral", "virus",
}


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


def tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) >= 5 and token not in GENERIC
    }


def profile_anchors(profile: dict) -> set[str]:
    anchors = tokens(profile.get("name") or "") | tokens(profile.get("scientificName") or "")
    slug = (profile.get("slug") or "").replace("-", " ")
    anchors |= tokens(slug)
    return anchors


def source_id(source: dict) -> str:
    if source.get("doi"):
        return f"doi:{source['doi'].strip().lower()}"
    if source.get("url"):
        return f"url:{source['url'].strip()}"
    raw = (source.get("title") or "") + "|" + (source.get("organization") or "")
    return "source:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def heldout_source_ids(path: pathlib.Path) -> set[str]:
    reserved = set()
    if not path.exists():
        return reserved
    for row in load_jsonl(path):
        for sid in row.get("must_cite") or []:
            value = (sid or "").strip()
            if value.startswith("doi:"):
                value = "doi:" + value[4:].lower()
            if value:
                reserved.add(value)
    return reserved


def audit(profiles: list[dict], heldout: set[str], limit: int = 5) -> dict:
    reviewed = [p for p in profiles if p.get("reviewStatus") == "reviewed" and p.get("id")]
    anchors_by_profile = {p["id"]: profile_anchors(p) for p in reviewed}
    owners_by_anchor: dict[str, set[str]] = defaultdict(set)
    for pid, anchors in anchors_by_profile.items():
        for anchor in anchors:
            owners_by_anchor[anchor].add(pid)

    foreign_only = []
    slots = 0
    profiles_with_context = 0
    for profile in reviewed:
        pid = profile["id"]
        target = anchors_by_profile[pid]
        claims = []
        seen = set()
        for source in profile.get("sources") or []:
            if source_id(source) in heldout:
                continue
            for claim in source.get("supportedClaims") or []:
                key = re.sub(r"\s+", " ", (claim or "").strip().lower())
                if not key or key in seen:
                    continue
                seen.add(key)
                claims.append({"claim": claim.strip(), "source_id": source_id(source)})
        selected = claims[:limit]
        if selected:
            profiles_with_context += 1
        for position, row in enumerate(selected, 1):
            slots += 1
            ctokens = tokens(row["claim"])
            current_hits = sorted(target & ctokens)
            foreign = sorted(
                token for token in ctokens
                if token in owners_by_anchor and any(owner != pid for owner in owners_by_anchor[token])
            )
            foreign = [token for token in foreign if token not in target]
            if foreign and not current_hits:
                foreign_only.append({
                    "profile_id": pid,
                    "position": position,
                    "source_id": row["source_id"],
                    "foreign_anchors": foreign,
                    "claim": row["claim"],
                })

    by_profile = Counter(item["profile_id"] for item in foreign_only)
    return {
        "reviewed_profiles": len(reviewed),
        "profiles_with_sft_context": profiles_with_context,
        "sft_context_slots_audited": slots,
        "foreign_only_context_slots": len(foreign_only),
        "foreign_only_rate": round(len(foreign_only) / slots, 6) if slots else 0.0,
        "profiles_with_foreign_only_context": len(by_profile),
        "top_profiles": by_profile.most_common(12),
        "examples": foreign_only[:20],
    }


def self_test() -> None:
    profiles = [
        {
            "id": "calcium-deficiency", "slug": "calcium-deficiency", "name": "Calcium deficiency",
            "reviewStatus": "reviewed", "sources": [{"url": "https://example.test/a", "supportedClaims": [
                "Calcium deficiency can affect developing tissues.",
                "Magnesium deficiency commonly presents differently in mobile tissues.",
            ]}],
        },
        {
            "id": "magnesium-deficiency", "slug": "magnesium-deficiency", "name": "Magnesium deficiency",
            "reviewStatus": "reviewed", "sources": [{"url": "https://example.test/b", "supportedClaims": [
                "Magnesium deficiency is a distinct nutrient disorder."
            ]}],
        },
    ]
    report = audit(profiles, set())
    assert report["sft_context_slots_audited"] == 3, report
    assert report["foreign_only_context_slots"] == 1, report
    assert report["examples"][0]["profile_id"] == "calcium-deficiency", report
    assert "magnesium" in report["examples"][0]["foreign_anchors"], report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    ap.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--max-foreign-only-rate", type=float)
    args = ap.parse_args()
    if args.self_test:
        self_test()
        print("sft profile relevance self-test passed")
        return 0
    try:
        report = audit(load_jsonl(args.input), heldout_source_ids(args.eval))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.max_foreign_only_rate is not None and report["foreign_only_rate"] > args.max_foreign_only_rate:
        print(
            f"foreign-only SFT context rate {report['foreign_only_rate']:.6f} exceeds allowed "
            f"{args.max_foreign_only_rate:.6f}", file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
