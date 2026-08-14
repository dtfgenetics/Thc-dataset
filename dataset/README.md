# THC Grow Doc dataset

This directory defines portable schemas and controlled snapshots for the plant-health diagnostic knowledge system. Application seed records currently live in `src/data/issues.ts` while the ingestion/API layer is being built.

## Separate data products

Do not collapse these into one folder or label:

1. Diagnostic knowledge database — symptoms, exclusions, look-alikes, confirmation, actions, prevention, and citations.
2. Licensed reference library — approved media that may be displayed to users.
3. Model-training dataset — separately approved media with explicit training eligibility and leakage-safe fixed splits.
4. Locked evaluation dataset — never used to train, tune, or select a model.
5. Acquisition control — source packages and raw-file state before individual assets are admitted.

## Controlled registry and acquisition

Drive remains the editable research-control source of truth; Git snapshots are reproducible review/release inputs.

- `catalog/` contains curated source/reference snapshots.
- `registry/` contains versioned dataset-registry snapshots.
- `acquisition/` contains snapshots of the Phase 0 raw-data acquisition manifest.
- `control/source-of-truth.json` identifies the controlled Drive resources.
- `schema/source.schema.json` defines source-level metadata.
- `schema/reference.schema.json` defines scientific reference/evidence metadata.
- `schema/acquisition.schema.json` defines acquisition-manifest records.
- `schema/asset.schema.json` defines acquired-file lineage, rights, grouping, confirmation and split metadata.
- `schema/media.schema.json` defines display/reference media records used by the application layer.

A verified scientific source is not the same thing as an acquired dataset, and an acquired file is not automatically training-ready. Rights, physical acquisition, provider checksum, SHA-256, perceptual duplicate review, source/plant/session/augmentation grouping, scientific review, and split safety must all pass before training eligibility.

## Media and asset admission

A cited webpage is not permission to copy its images. Display or training media must be public domain, carry a compatible license, have explicit written permission, or be owned by DTF Genetics.

Every approved visual asset must preserve:

- stable dataset/source/asset identifiers and original source location;
- creator, rights holder where known, license, required attribution and use limits;
- host species/context, organ/view/stage/severity and environmental context where known;
- confirmation method and evidence tier;
- SHA-256 plus perceptual hash;
- source-group, plant/session, temporal and parent/augmentation lineage where applicable;
- training eligibility and exactly one leakage-safe split when eligible.

User uploads are excluded from training by default and require separate opt-in. Cross-crop transfer imagery remains transfer evidence and cannot silently become cannabis causal ground truth. Viroid/virus/phytoplasma and many pathogen etiologies retain their laboratory-confirmation ceilings regardless of visual similarity.
