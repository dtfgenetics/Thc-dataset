# Acquisition snapshots

This directory stores versioned GitHub snapshots of the controlled Phase 0 acquisition manifest. The editable acquisition source of truth is the Google Sheet referenced by `dataset/control/source-of-truth.json`.

A source being registered or marked `READY TO FETCH` is **not** proof that its raw files were acquired. Acquisition is only complete after the exact source/version is pinned, rights are cleared for the intended lane, physical files are present, repository checksums are checked where available, local SHA-256 hashes are generated, images are perceptually deduplicated, source/plant/session/augmentation groups are preserved, and a leakage-safe split is assigned where training is allowed.

## Current snapshots

- `phase0-ds133-ds148.json` is the original verified Drive snapshot for DS-133 through DS-148.
- Later `v2`, `v3`, etc. files are immutable deltas. For a dataset ID, the highest-version delta that explicitly supersedes an earlier snapshot is the current acquisition state.
- Folder IDs point to the actual Drive destinations.
- Restricted, per-item, noncommercial, share-alike, provenance-uncertain, and quarantine sources stay outside the unrestricted raw lane.

## Concurrency-safe source-file IDs

The controlled Drive `Source_Files` table can be edited by multiple workstreams. Do not assume that the next sequential `SF-###` value remains free between read and write. New parallel ingestion work should prefer stable dataset-scoped IDs such as `SF-DS135-F03`, `SF-DS147-GBIF-<gbifID>`, or another deterministic source-specific identifier. Existing sequential IDs remain valid and must never be overwritten merely to restore numbering.

When a collision is discovered, preserve both legitimate records, allocate a non-colliding stable ID for the new record, update parent-manifest references, and add a new immutable Git delta rather than rewriting history.

## Required gates

1. Pin the exact version, DOI, revision, commit, or per-item identifier.
2. Archive the applicable license/rights evidence.
3. Acquire the bytes without converting a metadata-only record into an `acquired` claim.
4. Verify provider checksum when one exists and generate local SHA-256 for every retained file.
5. Generate perceptual hashes for visual assets and resolve exact/near duplicates.
6. Preserve `sourceGroupId`, plant/session identity, parent/augmentation lineage, and any temporal sequence identity.
7. Assign training/validation/test only after grouping; locked evaluation data can never become training eligible.
8. Preserve the scientific confirmation ceiling: cross-crop transfer data and visual-only cannabis references do not become causal ground truth by ingestion.

Run `npm run validate:acquisition` before committing a snapshot.
