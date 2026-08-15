# Training model starter

This folder is the first production-safe training scaffold for the cannabis/hemp symptom-image pipeline.

## Purpose

- build a manifest from the approved reference catalog
- define a transfer-learning starter for image classification
- enforce a conservative workflow before any production model is used

## Important rules

1. Do not train on user uploads without explicit opt-in.
2. Do not mix benchmark/evaluation data into training sets.
3. Keep plant/session/time-series groupings together when splitting data.
4. Train only on approved, license-safe, review-cleared references.
5. Hold out a benchmark set and never use it for tuning or model selection.

## Files

- `build_metadata_manifest.py` — creates a conservative file-level metadata manifest with dataset ID, label, group ID, dimensions, and hash
- `create_leakage_safe_split.py` — assigns train/val/test splits at the group level to avoid plant/session leakage
- `enrich_image_metadata.py` — computes pixel-level statistics (brightness, contrast, entropy, sharpness, aspect ratio, color means) for use in quality checks and downstream filtering
- `train_classifier.py` — minimal transfer-learning classifier starter that consumes the split manifest
- `requirements.txt` — Python dependencies for image model training

## Current generated data

- `metadata_manifest.csv` — raw image metadata for the acquired dataset files
- `leakage_safe_split.csv` — same rows with a leakage-safe split assignment
- `enriched_image_metadata.csv` — image-level pixel metadata generated from the split-safe manifest
- `enriched_image_metadata_summary.json` — aggregate statistics for the enriched metadata dataset

## Example

```bash
python training/build_metadata_manifest.py
python training/create_leakage_safe_split.py
python training/train_classifier.py --manifest training/leakage_safe_split.csv --image-root dataset/acquisition/acquired --split train
```

## Notes

- Labels are path-derived and should be human-reviewed before production use.
- Group-level splits are intentionally conservative: all images from the same plant, plant group, or time series remain together.
- This is still a starter pipeline; a future model should use a reviewed label taxonomy and a locked benchmark set before training for production accuracy.
