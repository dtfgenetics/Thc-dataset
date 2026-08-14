# Reusable Dataset Registry Snapshots

This directory stores versioned, editable GitHub snapshots of selected rows from the controlled THC Plant Diagnostic dataset registry.

## Source of truth

The authoritative editable research registry remains the Google Sheet identified in `dataset/control/source-of-truth.json`.

GitHub snapshots exist so code, reviews, pull requests and future deployment systems can consume stable metadata without depending on chat history.

## Current snapshot

`sources-132-146.json` contains DS-132 through DS-146, including:

- cannabis/hemp phenotyping and water-deficit evidence;
- cannabis morphology/genetic hard negatives;
- cannabis growth-stage localization;
- cross-crop phone/field sources for mildew, mites, virus-like symptoms, wilt and pest damage;
- a co-occurrence dataset useful for multi-label transfer;
- beneficial/non-pest insect negatives.

## Rules

- A source record is metadata, not proof that raw files were acquired.
- `VERIFIED METADATA` means source identity/metadata were checked; it does not mean every raw file passed checksum/provenance QA.
- Raw asset acquisition must be tracked separately in the acquisition manifest.
- Reference-only and restricted sources must never silently enter an open training release.
- Cross-crop etiologic labels are transfer evidence only; they do not confirm the same pathogen/virus in cannabis.
- Duplicate/derived data must remain grouped by original parent when building splits.
- Locked benchmark assets must never be used for training, tuning or model selection.

## Validation

Run:

```bash
npm run validate:sources
```

CI runs this validator before TypeScript checks, tests and production build.

## Updating snapshots

1. Update the controlled Drive registry first.
2. Export/copy the intended verified rows into a new versioned JSON snapshot.
3. Run the source validator.
4. Open a pull request and let CI pass before merging.
5. Never rewrite an old release snapshot to change history; add a new snapshot/version instead.
