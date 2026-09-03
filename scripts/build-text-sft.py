#!/usr/bin/env python3
"""Build leakage-aware Grow Doc text SFT candidates from reviewed diagnostic profiles.

This script intentionally generates candidates, not training-ready ground truth.
Human review must promote records from generated_unreviewed to reviewed.

Leakage control:
- profiles sharing any normalized DOI/URL source identifier are placed in one split group
- transitive source overlap is respected (A shares with B, B shares with C => A/B/C stay together)
- exact and normalized-message duplicates are removed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SYSTEM = (
    "You are Grow Doc, an evidence-grounded plant science assistant. "
    "Do not diagnose from one symptom alone. Separate observations from conclusions, "
    "state meaningful differentials, preserve uncertainty, and avoid treating "
    "experiment-specific numbers as universal thresholds."
)


class UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def stable_id(profile_id: str, lane: str, suffix: str) -> str:
    raw = f"{profile_id}|{lane}|{suffix}".encode()
    return f"gd-{hashlib.sha256(raw).hexdigest()[:16]}"


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    value = value.rstrip("/")
    return f"doi:{value}" if value else None


def doi_from_url(value: str | None) -> str | None:
    if not value:
        return None
    match = re.match(r"^https?://(?:dx\.)?doi\.org/(.+?)/?$", value.strip(), re.I)
    return normalize_doi(match.group(1)) if match else None


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"#.*$", "", value)
    value = value.rstrip("/")
    return f"url:{value.lower()}" if value else None


def source_keys(profile: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for source in profile.get("sources", []):
        doi = normalize_doi(source.get("doi")) or doi_from_url(source.get("url"))
        url = normalize_url(source.get("url"))
        if doi:
            keys.add(doi)
        if url and not url.startswith("url:https://doi.org/") and not url.startswith("url:http://doi.org/"):
            keys.add(url)
    return keys


def build_split_groups(profiles: list[dict[str, Any]]) -> dict[str, str]:
    ids = [p["id"] for p in profiles]
    uf = UnionFind(ids)
    owners: dict[str, str] = {}
    for profile in profiles:
        pid = profile["id"]
        for key in sorted(source_keys(profile)):
            if key in owners:
                uf.union(pid, owners[key])
            else:
                owners[key] = pid

    components: dict[str, list[str]] = defaultdict(list)
    for pid in ids:
        components[uf.find(pid)].append(pid)

    groups: dict[str, str] = {}
    for members in components.values():
        canonical_members = sorted(members)
        digest = hashlib.sha256("|".join(canonical_members).encode()).hexdigest()[:16]
        group = f"source-component-{digest}"
        for pid in members:
            groups[pid] = group
    return groups


def provenance(profile: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for s in profile.get("sources", []):
        out.append({
            "profileId": profile["id"],
            "sourceTitle": s.get("title", "Untitled source"),
            "doi": s.get("doi"),
            "url": s.get("url"),
            "supportedClaims": s.get("supportedClaims", []),
        })
    return out


def record(
    profile: dict[str, Any],
    split_group: str,
    lane: str,
    user: str,
    assistant: str,
    suffix: str,
) -> dict[str, Any]:
    return {
        "id": stable_id(profile["id"], lane, suffix),
        "lane": lane,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "provenance": provenance(profile),
        "evidenceTier": "A",
        "splitGroup": split_group,
        "reviewStatus": "generated_unreviewed",
        "metadata": {
            "profileId": profile["id"],
            "profileName": profile.get("name"),
            "category": profile.get("category"),
            "generator": "scripts/build-text-sft.py",
        },
    }


def build(profile: dict[str, Any], split_group: str) -> list[dict[str, Any]]:
    if profile.get("reviewStatus") != "reviewed" or not profile.get("sources"):
        return []
    name = profile.get("name", profile["id"])
    summary = profile.get("summary", "")
    indicators = profile.get("indicators", [])
    exclusions = profile.get("exclusions", [])
    confirm = profile.get("confirmation", [])
    warnings = profile.get("warnings", [])

    return [
        record(
            profile, split_group, "science_explanation",
            f"Explain {name} using the Grow Doc evidence base. Include uncertainty and avoid universal thresholds.",
            "\n\n".join(x for x in [
                summary,
                ("Observed indicators: " + "; ".join(indicators[:6])) if indicators else "",
                ("Important limitations: " + "; ".join(warnings[:3])) if warnings else "",
            ] if x),
            "science",
        ),
        record(
            profile, split_group, "diagnostic_reasoning",
            f"A grower suspects {name}. What observations support it, what look-alikes should be excluded, and what evidence would strengthen confirmation?",
            "\n\n".join(x for x in [
                ("Supporting observations: " + "; ".join(indicators[:6])) if indicators else "",
                ("Differentials/exclusions: " + "; ".join(exclusions[:6])) if exclusions else "",
                ("Confirmation steps: " + "; ".join(confirm[:5])) if confirm else "",
            ] if x),
            "diagnostic",
        ),
        record(
            profile, split_group, "grounded_qa",
            f"What should Grow Doc say if a user asks whether one photo is enough to confirm {name}?",
            "No. A single symptom photo should be treated as observational evidence, not definitive ground truth. "
            + (" ".join(confirm[:2]) if confirm else "Use contextual measurements, appropriate confirmation evidence, and differential diagnosis before confirming."),
            "single-photo",
        ),
    ]


def normalized_messages(row: dict[str, Any]) -> str:
    text = json.dumps(row["messages"], sort_keys=True, ensure_ascii=False)
    return re.sub(r"\s+", " ", text).strip().casefold()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default="data/profiles")
    ap.add_argument("--output", default="dataset/training/text-sft-candidates.jsonl")
    ap.add_argument("--report", default="dataset/training/text-sft-candidates.report.json")
    args = ap.parse_args()

    paths = [p for p in sorted(Path(args.profiles).glob("*.json")) if p.name != "index.json"]
    all_profiles = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    eligible = [
        profile for profile in all_profiles
        if profile.get("reviewStatus") == "reviewed" and profile.get("sources")
    ]

    split_groups = build_split_groups(eligible)
    records = []
    for profile in eligible:
        records.extend(build(profile, split_groups[profile["id"]]))

    seen_exact: set[str] = set()
    seen_normalized: set[str] = set()
    deduped = []
    exact_dropped = 0
    normalized_dropped = 0
    for row in records:
        exact = json.dumps(row["messages"], sort_keys=True, ensure_ascii=False)
        exact_digest = hashlib.sha256(exact.encode()).hexdigest()
        if exact_digest in seen_exact:
            exact_dropped += 1
            continue
        seen_exact.add(exact_digest)

        normalized_digest = hashlib.sha256(normalized_messages(row).encode()).hexdigest()
        if normalized_digest in seen_normalized:
            normalized_dropped += 1
            continue
        seen_normalized.add(normalized_digest)
        deduped.append(row)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in deduped), encoding="utf-8")

    group_counts = Counter(split_groups.values())
    report = {
        "profilesScanned": len(paths),
        "eligibleReviewedProfiles": len(eligible),
        "recordsBeforeDedup": len(records),
        "recordsAfterDedup": len(deduped),
        "exactDuplicatesDropped": exact_dropped,
        "normalizedDuplicatesDropped": normalized_dropped,
        "sourceComponents": len(group_counts),
        "largestSourceComponentProfiles": max(group_counts.values(), default=0),
        "lanes": dict(sorted(Counter(row["lane"] for row in deduped).items())),
        "output": str(out),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
