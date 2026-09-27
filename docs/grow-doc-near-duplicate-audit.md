# Grow Doc near-duplicate and contamination audit

This gate supplements exact-hash deduplication. It is intentionally conservative and provenance-preserving.

## Policy

- Normalize Unicode, case, whitespace, and punctuation before comparison.
- Compare token shingles for both prompt-only and prompt+answer representations.
- Use similarity only to flag records; never silently delete a training example.
- A verified near-duplicate crossing a training/evaluation boundary fails closed.
- Within-training matches are review items and retain record IDs, file/line locations, and available source/citation IDs.
- Empty or structurally incomplete records are not considered near-duplicates merely because both produce empty shingle sets.
- Threshold changes require reviewed positive/negative fixtures and regression tests.

## Current deterministic defaults

- prompt Jaccard threshold: `0.82`
- prompt+answer Jaccard threshold: `0.88`
- token shingle size: `3`

For small Grow Doc corpora, exhaustive pairwise verification is preferred because it is transparent and dependency-free. If corpus scale makes this expensive, MinHash/LSH may be added as a candidate-generation stage, but exact Jaccard verification and provenance-bearing reports remain required before any contamination decision.

## Verification

```bash
python scripts/audit-grow-doc-near-duplicates.py --self-test
python -m unittest tests/test_grow_doc_near_duplicate_audit.py -v
```

A real-corpus audit should explicitly pass the intended training and held-out JSONL lanes and write a reviewable report with `--report`. The audit must not modify source datasets.
