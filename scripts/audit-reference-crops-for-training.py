#!/usr/bin/env python3
"""Audit persisted Cannabis scientific panel crops for training admission.

This script deliberately does NOT promote media to trainingEligible=true. It identifies
which panel derivatives are ready for scientific review and which class-level blockers
must be resolved before a leakage-safe training split can exist.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CROPS_PATH = ROOT / "images" / "reference" / "crops-manifest.json"
PARENTS_PATH = ROOT / "images" / "reference" / "manifest.json"
OUT_PATH = ROOT / "dataset" / "training" / "reference-panel-admission-audit.json"

TRAINING_COMPATIBLE_LICENSES = {
    "CC BY 4.0",
    "CC BY 3.0",
    "CC BY 3.0 US",
    "CC BY",
    "Public domain (US federal government work)",
}
STRONG_CONFIRMATION_TOKENS = (
    "lab-confirmed",
    "controlled-nutrient",
    "controlled-pathogenicity",
    "molecular",
    "ploidy-confirmed",
    "genotype-linked",
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cannabis_host(crop: dict, parent: dict) -> bool:
    text = " ".join(
        str(v).lower()
        for v in [
            crop.get("host", ""),
            parent.get("host_species", ""),
            parent.get("host_context", ""),
            parent.get("caption", ""),
            parent.get("source_article", ""),
        ]
    )
    return "cannabis" in text or "hemp" in text


def strong_confirmation(crop: dict, parent: dict) -> bool:
    text = f"{crop.get('confirmation', '')} {parent.get('confirmation', '')}".lower()
    return any(token in text for token in STRONG_CONFIRMATION_TOKENS)


def reference_only_class(crop: dict) -> bool:
    if bool(crop.get("columnContext", {}).get("referenceOnlyClass")):
        return True
    slug = str(crop.get("issueSlug", "")).lower()
    return slug.endswith("-reference") or "reference-only" in str(crop.get("reason", "")).lower()


def main():
    crops_manifest = load(CROPS_PATH)
    parent_manifest = load(PARENTS_PATH)
    crops = crops_manifest.get("records", [])
    parents = {r["id"]: r for r in parent_manifest.get("records", [])}

    if not crops:
        raise SystemExit("No reference crops found")

    # First pass: immutable panel/source facts.
    provisional = []
    for crop in crops:
        parent = parents.get(crop.get("parentId"))
        if not parent:
            raise SystemExit(f"{crop.get('id')}: parentId not found in reference manifest")

        blockers = []
        if not cannabis_host(crop, parent):
            blockers.append("non_cannabis_or_unresolved_host")
        if parent.get("license") not in TRAINING_COMPATIBLE_LICENSES:
            blockers.append("license_not_training_compatible")
        if parent.get("intended_use") != "reference-only":
            blockers.append("unexpected_parent_use_state")
        if not strong_confirmation(crop, parent):
            blockers.append("confirmation_not_strong_enough_for_causal_seed")
        if crop.get("embeddedPanelLabel"):
            blockers.append("embedded_panel_label_shortcut_risk")
        if reference_only_class(crop):
            blockers.append("reference_only_or_unmaterialized_canonical_class")
        if not crop.get("sourceGroupId"):
            blockers.append("missing_source_group")
        if not crop.get("sha256") or not crop.get("perceptualHash"):
            blockers.append("missing_hashes")

        provisional.append(
            {
                "cropId": crop["id"],
                "issueSlug": crop.get("issueSlug"),
                "parentId": crop.get("parentId"),
                "parentPath": crop.get("parentPath"),
                "repositoryPath": crop.get("repositoryPath"),
                "sourceGroupId": crop.get("sourceGroupId"),
                "severity": crop.get("severity"),
                "view": crop.get("view"),
                "host": crop.get("host"),
                "confirmation": crop.get("confirmation"),
                "license": parent.get("license"),
                "sourceArticle": parent.get("source_article"),
                "requiredAttribution": parent.get("required_attribution"),
                "sha256": crop.get("sha256"),
                "perceptualHash": crop.get("perceptualHash"),
                "panelReviewCandidate": len(blockers) == 0,
                "trainingEligible": False,
                "datasetSplit": "none",
                "blockers": blockers,
            }
        )

    # Class-level independence: one paper/figure cannot establish a deployable class.
    eligible_groups_by_issue = collections.defaultdict(set)
    total_groups_by_issue = collections.defaultdict(set)
    counts_by_issue = collections.Counter()
    for rec in provisional:
        issue = rec["issueSlug"] or "__missing__"
        counts_by_issue[issue] += 1
        if rec.get("sourceGroupId"):
            total_groups_by_issue[issue].add(rec["sourceGroupId"])
            if rec["panelReviewCandidate"]:
                eligible_groups_by_issue[issue].add(rec["sourceGroupId"])

    class_reviews = []
    for issue in sorted(counts_by_issue):
        eligible_groups = sorted(eligible_groups_by_issue[issue])
        total_groups = sorted(total_groups_by_issue[issue])
        blockers = []
        if not eligible_groups:
            blockers.append("no_panel_review_candidates")
        if len(eligible_groups) < 2:
            blockers.append("fewer_than_two_independent_eligible_source_groups")
        # A trustworthy held-out benchmark should not be carved out of the same scientific figure.
        if len(eligible_groups) < 3:
            blockers.append("insufficient_independent_groups_for_train_validation_locked_eval_design")

        class_reviews.append(
            {
                "issueSlug": issue,
                "panelCount": counts_by_issue[issue],
                "sourceGroupCount": len(total_groups),
                "eligibleSourceGroupCount": len(eligible_groups),
                "eligibleSourceGroupIds": eligible_groups,
                "classAdmissionStatus": "independence_review_possible" if not blockers else "collection_required",
                "classBlockers": blockers,
                "nextAction": (
                    "Scientific review, duplicate/source-family check, then assign whole source groups to leakage-safe partitions."
                    if not blockers
                    else "Collect additional independent Cannabis/hemp cases from different plants/sessions/sources before class training admission."
                ),
            }
        )

    review_candidate_count = sum(1 for r in provisional if r["panelReviewCandidate"])
    blocker_counts = collections.Counter(b for r in provisional for b in r["blockers"])
    class_status_counts = collections.Counter(r["classAdmissionStatus"] for r in class_reviews)

    audit = {
        "schemaVersion": "1.0.0",
        "generatedFrom": [
            str(CROPS_PATH.relative_to(ROOT)),
            str(PARENTS_PATH.relative_to(ROOT)),
        ],
        "policy": {
            "trainingPromotion": "This audit never sets trainingEligible=true.",
            "sourceGrouping": "Every crop derived from the same scientific figure/sourceGroupId must remain in one partition.",
            "independence": "At least two independent eligible source groups are required before class-level training admission is considered; three are preferred to support train/validation/locked-evaluation separation.",
            "causalCeiling": "Virus/viroid and etiologically ambiguous pathogen panels remain subject to laboratory/molecular confirmation ceilings even when used as reference features.",
            "referenceVsTraining": "CC-BY or public-domain rights are necessary but not sufficient; scientific confirmation, host relevance, shortcut review, deduplication and split safety are separate gates.",
        },
        "summary": {
            "panelCropCount": len(provisional),
            "sourceGroupCount": len({r["sourceGroupId"] for r in provisional if r.get("sourceGroupId")}),
            "panelReviewCandidateCount": review_candidate_count,
            "blockedPanelCount": len(provisional) - review_candidate_count,
            "trainingEligibleCount": 0,
            "classCount": len(class_reviews),
            "classStatusCounts": dict(sorted(class_status_counts.items())),
            "panelBlockerCounts": dict(sorted(blocker_counts.items())),
        },
        "classReviews": class_reviews,
        "panels": sorted(provisional, key=lambda r: r["cropId"]),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(audit["summary"], indent=2))


if __name__ == "__main__":
    main()
