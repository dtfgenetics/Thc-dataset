#!/usr/bin/env python3
"""Build leakage-aware Grow Doc text SFT candidates from reviewed diagnostic profiles.

This script intentionally generates candidates, not training-ready ground truth.
Human review must promote records from generated_unreviewed to reviewed.
"""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SYSTEM = (
    "You are Grow Doc, an evidence-grounded plant science assistant. "
    "Do not diagnose from one symptom alone. Separate observations from conclusions, "
    "state meaningful differentials, preserve uncertainty, and avoid treating "
    "experiment-specific numbers as universal thresholds."
)


def stable_id(profile_id: str, lane: str, suffix: str) -> str:
    raw = f"{profile_id}|{lane}|{suffix}".encode()
    return f"gd-{hashlib.sha256(raw).hexdigest()[:16]}"


def source_group(profile: dict[str, Any]) -> str:
    dois = sorted({s.get("doi") for s in profile.get("sources", []) if s.get("doi")})
    urls = sorted({s.get("url") for s in profile.get("sources", []) if s.get("url")})
    key = "|".join(dois or urls or [profile["id"]])
    return f"source-{hashlib.sha256(key.encode()).hexdigest()[:16]}"


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


def record(profile: dict[str, Any], lane: str, user: str, assistant: str, suffix: str) -> dict[str, Any]:
    return {
        "id": stable_id(profile["id"], lane, suffix),
        "lane": lane,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "provenance": provenance(profile),
        "evidenceTier": "A" if profile.get("reviewStatus") == "reviewed" and profile.get("sources") else "reference_only",
        "splitGroup": source_group(profile),
        "reviewStatus": "generated_unreviewed",
        "metadata": {
            "profileId": profile["id"],
            "profileName": profile.get("name"),
            "category": profile.get("category"),
            "generator": "scripts/build-text-sft.py",
        },
    }


def build(profile: dict[str, Any]) -> list[dict[str, Any]]:
    if profile.get("reviewStatus") != "reviewed" or not profile.get("sources"):
        return []
    name = profile.get("name", profile["id"])
    summary = profile.get("summary", "")
    indicators = profile.get("indicators", [])
    exclusions = profile.get("exclusions", [])
    confirm = profile.get("confirmation", [])
    warnings = profile.get("warnings", [])

    rows = []
    rows.append(record(
        profile,
        "science_explanation",
        f"Explain {name} using the Grow Doc evidence base. Include uncertainty and avoid universal thresholds.",
        "\n\n".join(x for x in [
            summary,
            ("Observed indicators: " + "; ".join(indicators[:6])) if indicators else "",
            ("Important limitations: " + "; ".join(warnings[:3])) if warnings else "",
        ] if x),
        "science",
    ))
    rows.append(record(
        profile,
        "diagnostic_reasoning",
        f"A grower suspects {name}. What observations support it, what look-alikes should be excluded, and what evidence would strengthen confirmation?",
        "\n\n".join(x for x in [
            ("Supporting observations: " + "; ".join(indicators[:6])) if indicators else "",
            ("Differentials/exclusions: " + "; ".join(exclusions[:6])) if exclusions else "",
            ("Confirmation steps: " + "; ".join(confirm[:5])) if confirm else "",
        ] if x),
        "diagnostic",
    ))
    rows.append(record(
        profile,
        "grounded_qa",
        f"What should Grow Doc say if a user asks whether one photo is enough to confirm {name}?",
        "No. A single symptom photo should be treated as observational evidence, not definitive ground truth. "
        + (" ".join(confirm[:2]) if confirm else "Use contextual measurements, appropriate confirmation evidence, and differential diagnosis before confirming."),
        "single-photo",
    ))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default="data/profiles")
    ap.add_argument("--output", default="dataset/training/text-sft-candidates.jsonl")
    args = ap.parse_args()

    records = []
    paths = sorted(Path(args.profiles).glob("*.json"))
    for path in paths:
        if path.name == "index.json":
            continue
        profile = json.loads(path.read_text(encoding="utf-8"))
        records.extend(build(profile))

    seen = set()
    deduped = []
    for row in records:
        payload = json.dumps(row["messages"], sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        deduped.append(row)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in deduped), encoding="utf-8")
    print(json.dumps({"profilesScanned": len(paths), "records": len(deduped), "output": str(out)}))


if __name__ == "__main__":
    main()
