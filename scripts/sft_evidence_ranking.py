#!/usr/bin/env python3
"""Deterministic target-aware ranking for profile-specific SFT evidence.

Reviewed claims remain in the global RAG corpus. This module only orders the small evidence
window supplied to profile-specific SFT examples so target-explicit evidence is preferred,
DOI-backed scientific evidence wins ties within the same relevance tier, neutral evidence remains
available, and claims explicitly naming a different diagnostic target are deprioritized.
It intentionally uses only corpus-side profile metadata and claim/source metadata.
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


def provenance_tier(row: dict) -> int:
    """Return a conservative provenance preference for SFT evidence ordering.

    A DOI-backed source is preferred because it provides a stable scholarly identity that can be
    independently checked and leakage-audited. URL-only institutional/extension material remains
    available to retrieval and may still enter SFT when it is the best target-relevant evidence;
    it is simply not allowed to outrank equally relevant DOI-backed evidence. Missing source
    metadata sorts last and is expected to be caught by upstream corpus integrity validation.
    """
    source = row.get("source") or {}
    source_id = str(row.get("source_id") or "").strip().lower()
    if source.get("doi") or source_id.startswith("doi:"):
        return 0
    if source.get("url") or source_id.startswith("url:"):
        return 1
    return 2


def rank_sft_evidence(profile: dict, rows: list[dict], owners_by_anchor: dict[str, set[str]]) -> list[dict]:
    """Return rows ordered by target relevance, then provenance strength, without dropping data."""
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
        # Target-explicit first, neutral second, explicit foreign-target last. Within a relevance
        # tier, prefer DOI-backed evidence before URL-only support material.
        tier = 0 if target_hits else (2 if foreign_hits else 1)
        ranked.append((
            tier,
            provenance_tier(row),
            -len(target_hits),
            len(foreign_hits),
            index,
            row,
        ))
    ranked.sort(key=lambda item: item[:5])
    return [item[-1] for item in ranked]


def self_test() -> None:
    profiles = [
        {"id": "calcium", "name": "Calcium deficiency", "slug": "calcium-deficiency", "reviewStatus": "reviewed"},
        {"id": "magnesium", "name": "Magnesium deficiency", "slug": "magnesium-deficiency", "reviewStatus": "reviewed"},
    ]
    owners = build_anchor_owners(profiles)
    rows = [
        {"claim": "Magnesium deficiency can affect older leaves.", "source_id": "doi:10.example/foreign", "source": {"doi": "10.example/foreign"}},
        {"claim": "Nutrient disorders can produce overlapping visual symptoms.", "source_id": "doi:10.example/neutral", "source": {"doi": "10.example/neutral"}},
        {"claim": "Calcium deficiency can affect developing tissues.", "source_id": "url:https://extension.example/calcium", "source": {"url": "https://extension.example/calcium"}},
        {"claim": "Calcium deficiency can reduce growth in developing tissues.", "source_id": "doi:10.example/calcium", "source": {"doi": "10.example/calcium"}},
    ]
    ranked = rank_sft_evidence(profiles[0], rows, owners)
    assert [row["source_id"] for row in ranked] == [
        "doi:10.example/calcium",
        "url:https://extension.example/calcium",
        "doi:10.example/neutral",
        "doi:10.example/foreign",
    ], ranked
    assert provenance_tier({"source_id": "doi:10.x/a", "source": {}}) == 0
    assert provenance_tier({"source_id": "url:https://example.org/a", "source": {}}) == 1
    assert provenance_tier({"source_id": "source:unknown", "source": {}}) == 2


if __name__ == "__main__":
    self_test()
    print("sft evidence ranking self-test passed")
