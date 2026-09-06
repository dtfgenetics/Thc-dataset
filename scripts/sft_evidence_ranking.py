#!/usr/bin/env python3
"""Deterministic target-aware ranking for profile-specific SFT evidence.

Reviewed claims remain in the global RAG corpus. This module only orders the small evidence
window supplied to profile-specific SFT examples so target-explicit evidence is preferred,
neutral evidence remains available, and claims explicitly naming a different diagnostic target
are deprioritized. It intentionally uses only corpus-side profile metadata and claim text.
"""
from __future__ import annotations

import re
from collections import defaultdict

GENERIC = {
    "abiotic", "associated", "bacterial", "blight", "cannabis", "complex", "context",
    "cultivation", "deficiency", "disease", "disorder", "environmental", "exposure",
    "feeding", "flower", "fungal", "fungus", "growth", "hemp", "high", "injury", "leaf",
    "leaves", "light", "mold", "nutrient", "other", "pathogen", "plant", "plants",
    "response", "root", "sativa", "species", "spot", "state", "stress", "symptom",
    "symptoms", "toxicity", "viral", "virus", "visual", "water", "white",
}


def tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) >= 5 and token not in GENERIC
    }


def profile_anchors(profile: dict) -> set[str]:
    anchors = tokens(profile.get("name") or "") | tokens(profile.get("scientificName") or "")
    anchors |= tokens((profile.get("slug") or "").replace("-", " "))
    return anchors


def build_anchor_owners(profiles: list[dict]) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = defaultdict(set)
    for profile in profiles:
        pid = profile.get("id")
        if profile.get("reviewStatus") != "reviewed" or not pid:
            continue
        for anchor in profile_anchors(profile):
            owners[anchor].add(pid)
    return dict(owners)


def rank_sft_evidence(profile: dict, rows: list[dict], owners_by_anchor: dict[str, set[str]]) -> list[dict]:
    """Return rows ordered by conservative target relevance without dropping provenance."""
    pid = profile.get("id")
    target = profile_anchors(profile)
    ranked = []
    for index, row in enumerate(rows):
        ctokens = tokens(row.get("claim") or "")
        target_hits = target & ctokens
        foreign_hits = {
            token for token in ctokens
            if token in owners_by_anchor
            and token not in target
            and any(owner != pid for owner in owners_by_anchor[token])
        }
        # Target-explicit first, neutral second, explicit foreign-target last.
        tier = 0 if target_hits else (2 if foreign_hits else 1)
        ranked.append((tier, -len(target_hits), len(foreign_hits), index, row))
    ranked.sort(key=lambda item: item[:4])
    return [item[-1] for item in ranked]


def self_test() -> None:
    profiles = [
        {"id": "calcium", "name": "Calcium deficiency", "slug": "calcium-deficiency", "reviewStatus": "reviewed"},
        {"id": "magnesium", "name": "Magnesium deficiency", "slug": "magnesium-deficiency", "reviewStatus": "reviewed"},
    ]
    owners = build_anchor_owners(profiles)
    rows = [
        {"claim": "Magnesium deficiency can affect older leaves.", "source_id": "foreign"},
        {"claim": "Nutrient disorders can produce overlapping visual symptoms.", "source_id": "neutral"},
        {"claim": "Calcium deficiency can affect developing tissues.", "source_id": "target"},
    ]
    ranked = rank_sft_evidence(profiles[0], rows, owners)
    assert [row["source_id"] for row in ranked] == ["target", "neutral", "foreign"], ranked


if __name__ == "__main__":
    self_test()
    print("sft evidence ranking self-test passed")
