# Near-duplicate audit implementation notes

- Added dependency-free token-shingle/Jaccard near-duplicate detection.
- Preserves record and source/citation identities in reports.
- Train/evaluation overlap fails closed; within-training overlap is review-only.
- Added regression protection for empty-text records to prevent false 1.0-Jaccard matches.
- Added standalone regression tests and a canonical local/CI validation runner.
- Added a dedicated GitHub Actions workflow scoped to the auditor and its tests.

Pending: exact-head CI verification and a real-corpus threshold calibration report before merge.
