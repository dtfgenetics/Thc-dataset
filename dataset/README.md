# THC Grow Doc dataset

This directory defines the portable schemas for issue knowledge and licensed reference media. The application seed records currently live in `src/data/issues.ts` while the ingestion and API layer are being built.

## Separate data products

Do not collapse these into one folder or label:

1. Diagnostic knowledge database — symptoms, exclusions, look-alikes, confirmation, actions, prevention, and citations.
2. Licensed reference library — approved media that may be displayed to users.
3. Model-training dataset — separately approved media with explicit training eligibility and a fixed split.
4. Locked evaluation dataset — never used to train, tune, or select a model.

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
