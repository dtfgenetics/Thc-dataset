# THC Grow Doc dataset

This directory defines portable schemas and controlled snapshots for the plant-health diagnostic knowledge system. Application seed records currently live in `src/data/issues.ts` while the ingestion/API layer is being built.

## Separate data products

Do not collapse these into one folder or label:

1. Diagnostic knowledge database — symptoms, exclusions, look-alikes, confirmation, actions, prevention, and citations.
2. Licensed reference library — approved media that may be displayed to users.
3. Diagnostic case store — user evidence, measurements, structured observations, predictions, outcomes, and consent.
4. Independent review store — human verification, final labels, error classes, and dataset-promotion decisions.
5. Model-training dataset — separately approved media/cases with explicit training eligibility and leakage-safe fixed splits.
6. Locked evaluation dataset — confirmed examples never used to train, tune, prompt-select, threshold-tune, or choose a model.
7. Acquisition control — source packages and raw-file state before individual assets are admitted.

## Schemas

- `schema/issue.schema.json` — canonical plant-health issue knowledge records.
- `schema/media.schema.json` — licensed display/reference media records used by the application layer.
- `schema/case.schema.json` — one diagnostic interaction, including evidence, grow context, observations, predictions, verification, outcome, and explicit consent.
- `schema/review.schema.json` — independent case review, error classification, and Candidate/Silver/Gold promotion eligibility.
- `schema/evaluation.schema.json` — immutable confirmed evaluation examples with recorded model/ruleset runs.
- `schema/sex-observation.schema.json` — serial reproductive sex-expression observations tied to visible structures and later confirmation.
- `schema/source.schema.json` — source-level metadata.
- `schema/reference.schema.json` — scientific reference/evidence metadata.
- `schema/acquisition.schema.json` — acquisition-manifest records.
- `schema/asset.schema.json` — acquired-file lineage, rights, grouping, confirmation, and split metadata.

## Trust model

An AI or ruleset prediction is never ground truth. Diagnostic verification and dataset promotion are separate decisions.

The default diagnostic evidence lifecycle is:

`candidate -> user-supported -> evidence-supported -> expert-verified -> lab/directly confirmed where applicable`

Dataset-promotion tiers are:

- **Candidate** — unverified submissions or predictions; never treated as training truth by default.
- **Silver** — reviewed, strongly evidence-supported records that do not meet the strongest available confirmation level.
- **Gold** — expert/direct/laboratory-confirmed records as appropriate to the label, with complete provenance and review.
- **Locked evaluation** — protected confirmed examples excluded from training, retrieval tuning, prompt selection, threshold tuning, and model selection.

User-reported improvement is useful supporting evidence but does not by itself prove a diagnosis.

## Controlled registry and acquisition

Drive remains the editable research-control source of truth; Git snapshots are reproducible review/release inputs.

- `catalog/` contains curated source/reference snapshots.
- `registry/` contains versioned dataset-registry snapshots.
- `acquisition/` contains snapshots of the Phase 0 raw-data acquisition manifest.
- `control/source-of-truth.json` identifies the controlled Drive resources.

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

## Reproductive sex-expression data

Classify visible reproductive expression rather than inferring sex from seedling shape, plant height, vigor, or leaf form. Serial observations are preferred because an early `too-early` or probable classification can later be paired with directly visible pistillate, staminate, or co-sexual structures on the same plant.
