# Bulk acquisition engine

Bulk acquisition runs on GitHub-hosted runners because the chat/container runtime may not have reliable outbound DNS or binary transfer support.

## Phase 1

The first executable batch targets:

- **DS-090** — pinned industrial-hemp growth/water-stress repository; verify the exact Git commit and seven source tree SHAs, hash every retained file, preserve plant/time-series grouping, and package the published model as reproducibility-only metadata.
- **DS-071** — Cannabis single-element nutrient-deficiency supplementary ZIP; retrieve through Europe PMC with an MDPI CDN fallback, verify ZIP structure, and preserve treatment/week/organ provenance.
- **DS-165** — USDA-ARS public-domain broad-mite micrograph; verify the provider SHA-1 and exact byte size before admitting it.

Successful bytes are published as GitHub Release assets under `bulk-acquisition-phase1-2026-08-14` and also retained as a GitHub Actions artifact for the run. The generated `phase1-manifest.json` is the truth record for the batch: only `status=acquired` means the release actually contains verified bytes.

This storage layer does **not** bypass scientific or dataset safety rules. Cross-crop/organism images remain transfer/reference material, DS-090 must be re-split by plant/time-series rather than its published random split, and visual nutrient progression does not become image-only causal proof.
