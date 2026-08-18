#!/usr/bin/env python3
"""Identify persisted scientific reference originals that lack reviewed panel crops."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENTS_PATH = ROOT / "images" / "reference" / "manifest.json"
CROPS_PATH = ROOT / "images" / "reference" / "crops-manifest.json"
OUT_PATH = ROOT / "dataset" / "training" / "unpanelized-reference-originals.json"

HIGH_VALUE_TERMS = (
    "cannabis", "hemp", "deficien", "toxicity", "aphid", "mite", "fusarium", "botrytis",
    "powdery", "mildew", "pythium", "hlvd", "viroid", "virus", "bctv", "root", "rot",
    "intersex", "male", "female", "senescence", "light", "water", "salinity", "stress"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def text(parent: dict) -> str:
    return " ".join(str(parent.get(k, "")).lower() for k in (
        "id", "issue_slug", "diagnostic_label", "caption", "host_species", "host_context", "source_article", "stage"
    ))


def main():
    parents = load(PARENTS_PATH).get("records", [])
    crops = load(CROPS_PATH).get("records", [])
    cropped_parent_ids = {c.get("parentId") for c in crops if c.get("parentId")}
    crop_counts = {}
    for crop in crops:
        crop_counts[crop["parentId"]] = crop_counts.get(crop["parentId"], 0) + 1

    rows = []
    for parent in parents:
        pid = parent.get("id")
        blob = text(parent)
        cannabis_domain = "cannabis" in blob or "hemp" in blob
        organism_only = str(parent.get("host_context", "")).lower() == "organism-only"
        already_cropped = pid in cropped_parent_ids
        high_value = cannabis_domain and not organism_only and any(term in blob for term in HIGH_VALUE_TERMS)

        if already_cropped:
            status = "panelized"
            action = "Keep source-grouped; use the training-admission audit for next gates."
        elif high_value:
            status = "panelization_review_required"
            action = "Review figure geometry/caption, define diagnostic panel bounds, preserve sourceGroupId, then generate hashed reference-only crops."
        elif cannabis_domain:
            status = "reference_review_required"
            action = "Review whether the original contains a useful diagnostic/negative panel before adding crop geometry."
        else:
            status = "not_cannabis_panel_priority"
            action = "Keep in expert/transfer reference role; do not create Cannabis causal panels by default."

        rows.append({
            "parentId": pid,
            "issueSlug": parent.get("issue_slug"),
            "repositoryPath": parent.get("repository_path"),
            "sourceArticle": parent.get("source_article"),
            "hostSpecies": parent.get("host_species"),
            "hostContext": parent.get("host_context"),
            "confirmation": parent.get("confirmation"),
            "license": parent.get("license"),
            "sha256": parent.get("sha256"),
            "existingCropCount": crop_counts.get(pid, 0),
            "status": status,
            "priority": "P0" if status == "panelization_review_required" else ("P1" if status == "reference_review_required" else "P2"),
            "nextAction": action,
            "trainingEligible": False,
        })

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    result = {
        "schemaVersion": "1.0.0",
        "policy": "Persisted originals are not automatically cropped or training-eligible. New crop geometry requires scientific/figure review, and all derivatives inherit source grouping and rights constraints.",
        "summary": {
            "persistedOriginalCount": len(rows),
            "currentlyPanelizedOriginalCount": sum(1 for r in rows if r["status"] == "panelized"),
            "unpanelizedOriginalCount": sum(1 for r in rows if r["status"] != "panelized"),
            "p0PanelizationReviewCount": sum(1 for r in rows if r["status"] == "panelization_review_required"),
            "statusCounts": counts,
        },
        "records": sorted(rows, key=lambda r: (r["priority"], r["parentId"] or "")),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
