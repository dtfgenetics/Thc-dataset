# Dataset catalog

This directory is the Git-versioned mirror of the controlled THC Plant Diagnostic source system.

## Source of truth

The editable control plane remains the Google Drive workbook **THC Plant Diagnostic — Public Dataset Registry v1.0 — CONTROLLED**. GitHub snapshots are intentionally versioned so app code, tests, model builds, and releases can point to a reproducible source set instead of a moving spreadsheet.

## Files

- `control.json` — identifies the controlled registry and the scope/date of the current Git snapshot.
- `p0-cannabis-sources.json` — highest-priority cannabis/hemp sources currently admitted to the controlled registry.
- `../schema/source.schema.json` — schema for source-level dataset/reference records.
- `../schema/reference.schema.json` — schema for scientific reference-image/evidence records.
- `../schema/media.schema.json` — asset-level schema. A source citation is not an image license.

## Admission rules

A source may be useful without being training-eligible. Keep these lanes separate:

1. **Training-ready data** — raw files are actually acquired, hashed, licensed for the intended use, deduplicated, normalized, and assigned leakage-safe splits.
2. **Licensed reference images** — useful for user-facing comparison or RAG, but not automatically training-eligible.
3. **Confirmation evidence** — controlled inoculation, pathology, PCR/RT-qPCR, sequencing, physiology, tissue analysis, microscopy, or similar evidence that constrains what the app may claim.
4. **Transfer-only data** — non-cannabis images used for representation learning or hard negatives; never relabeled as cannabis ground truth.
5. **Rights hold / author request** — scientifically valuable but not reusable until raw files and permission are obtained.

Never mark a dataset `acquired` merely because a DOI, article, GitHub project, or download page exists. Acquisition means the actual files are stored, checksummed, provenance-linked, and rights-gated.
