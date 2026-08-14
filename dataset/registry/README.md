# Reusable Dataset Registry Snapshots

This directory stores versioned, editable GitHub snapshots of selected rows from the controlled THC Plant Diagnostic dataset registry.

## Source of truth

The authoritative editable research registry remains the Google Sheet identified in `dataset/control/source-of-truth.json`.

GitHub snapshots exist so code, reviews, pull requests and future deployment systems can consume stable metadata without depending on chat history.

## Current snapshots

`sources-132-146.json` contains DS-132 through DS-146, including:

- cannabis/hemp phenotyping and water-deficit evidence;
- cannabis morphology/genetic hard negatives;
- cannabis growth-stage localization;
- cross-crop phone/field sources for mildew, mites, virus-like symptoms, wilt and pest damage;
- a co-occurrence dataset useful for multi-label transfer;
- beneficial/non-pest insect negatives.

`sources-147-158.json` contains DS-147 through DS-158, including:

- GBIF and iNaturalist item-licensed biodiversity-media acquisition pools;
- leaf instance-segmentation transfer data;
- several cannabis-specific root/crown pathogen and Fusarium studies;
- cannabis aphid biocontrol evidence;
- russet-mite microscopy raw-photo acquisition candidate;
- UC Kearney hemp arthropod voucher/digitization partnership candidate.

`sources-159-160.json` contains the next direct-cannabis localization candidates:

- DS-159 Cannabis Leaf Counter — leaf/plant object detection;
- DS-160 Plant-Leave-single — plant/node/leaf/meristem instance segmentation.

Both DS-159 and DS-160 remain provenance/dedup quarantine candidates until an exact source version is pinned and source-family/augmentation relationships are verified.

## Rules

- A source record is metadata, not proof that raw files were acquired.
- `VERIFIED METADATA` means source identity/metadata were checked; it does not mean every raw file passed checksum/provenance QA.
- Raw asset acquisition must be tracked separately in the acquisition manifest.
- Reference-only and restricted sources must never silently enter an open training release.
- Cross-crop etiologic labels are transfer evidence only; they do not confirm the same pathogen/virus in cannabis.
- Duplicate/derived data must remain grouped by original parent when building splits.
- Locked benchmark assets must never be used for training, tuning or model selection.
- Author-request and partner-request candidates stay outside training until explicit media/data rights are documented.
- Roboflow forks, generated versions and augmented/resized exports must be treated as one source family until dedup/provenance review proves otherwise.

## Validation

Run:

```bash
npm run validate:sources
```

CI validates every listed snapshot before TypeScript checks, tests and production build.

## Updating snapshots

1. Update the controlled Drive registry first.
2. Export/copy the intended verified rows into a new versioned JSON snapshot.
3. Add the new snapshot path to `validate:sources`.
4. Run the source validator.
5. Open a pull request and let CI pass before merging.
6. Never rewrite an old release snapshot to change history; add a new snapshot/version instead.
