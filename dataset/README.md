# THC Grow Doc dataset

This directory defines the portable schemas for issue knowledge and licensed reference media. The application seed records currently live in `src/data/issues.ts` while the ingestion and API layer are being built.

## Separate data products

Do not collapse these into one folder or label:

1. Diagnostic knowledge database — symptoms, exclusions, look-alikes, confirmation, actions, prevention, and citations.
2. Licensed reference library — approved media that may be displayed to users.
3. Model-training dataset — separately approved media with explicit training eligibility and a fixed split.
4. Locked evaluation dataset — never used to train, tune, or select a model.

## Catalog and controlled registry

`catalog/` now mirrors the controlled project registry into Git so app builds and model work can reference reproducible source snapshots. Drive remains the editable control plane; Git snapshots are release inputs.

- `catalog/control.json` identifies the controlled registry and snapshot scope.
- `catalog/p0-cannabis-sources.json` contains the highest-priority cannabis/hemp sources admitted at the snapshot date.
- `schema/source.schema.json` defines source-level records.
- `schema/reference.schema.json` defines scientific reference/evidence records.
- `schema/media.schema.json` remains the individual asset schema.

A verified scientific source is not the same thing as an acquired training dataset. Rights, raw-file acquisition, hashing, duplicate review, grouping, and split safety must all pass before an image becomes training-ready.

## Media admission

A cited webpage is not permission to copy its images. Display or training media must be public domain, carry a compatible license, have explicit written permission, or be owned by DTF Genetics.

Every approved media record requires:

- stable asset and issue identifiers;
- original and derivative locations;
- source, creator, license, and required attribution;
- organ, view, stage, and severity when known;
- confirmation method and scientific review status;
- training eligibility and exactly one dataset split when eligible;
- SHA-256 and perceptual hashes for integrity and duplicate detection.

User uploads are not eligible for training by default.
