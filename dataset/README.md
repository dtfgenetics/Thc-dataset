# THC Grow Doc dataset

This directory defines the portable data contracts for the THC Grow Doc diagnostic system. The application seed records currently live in `src/data/issues.ts` while the ingestion, persistence, review, and API layers are being built.

## Separate data products

Do not collapse these into one folder, table, or trust label:

1. **Diagnostic knowledge database** — symptoms, exclusions, look-alikes, confirmation, actions, prevention, and citations.
2. **Licensed reference library** — approved media that may be displayed to users.
3. **Diagnostic case store** — user evidence, measurements, structured observations, model/ruleset predictions, follow-up, and consent.
4. **Review and verification store** — independent human review, final labels, error classes, and dataset-promotion decisions.
5. **Model-training dataset** — separately approved media/cases with explicit training eligibility and a fixed split.
6. **Locked evaluation dataset** — confirmed examples never used to train, tune, prompt-select, or choose a model.

## Schemas

- `schema/issue.schema.json` — canonical plant-health issue knowledge record.
- `schema/media.schema.json` — licensed reference/training media provenance and permissions.
- `schema/case.schema.json` — one diagnostic interaction, including evidence, context, observations, predictions, outcome, and user consent.
- `schema/review.schema.json` — independent review and Candidate/Silver/Gold promotion decision.
- `schema/evaluation.schema.json` — immutable ground-truth example used to measure model performance.
- `schema/sex-observation.schema.json` — serial reproductive sex-expression observations tied to visible organs and later confirmation.

## Trust model

An AI prediction is never ground truth.

The default lifecycle is:

`candidate -> user-supported -> evidence-supported -> expert-verified -> lab/directly confirmed where applicable`

Dataset promotion is separate from diagnostic status:

- **Candidate** — unverified submissions and predictions. Not trusted as training truth.
- **Silver** — strongly evidence-supported and reviewed, but not at the strongest available confirmation level.
- **Gold** — expert/direct/laboratory confirmed as appropriate to the label, with complete provenance and review.
- **Locked evaluation** — a protected confirmed subset that is excluded from training and tuning.

User-reported improvement is useful supporting evidence but does not by itself prove a diagnosis.

## Reproductive sex-expression data

The system should classify visible reproductive expression rather than infer sex from seedling shape, plant height, vigor, or leaf form. Serial observations are preferred because an early `too-early` or probable classification can later be paired with directly visible pistillate, staminate, or co-sexual reproductive structures on the same plant.

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

User uploads are not eligible for training by default. A case may become training-eligible only after explicit consent, evidence review, licensing/ownership checks, de-identification where needed, and a separate promotion decision.

## Evaluation rule

The locked evaluation set is the measurement instrument for the diagnostic system. Its cases must not be used for model training, prompt tuning, ruleset tuning, threshold tuning, or manual selection of a preferred model. Each evaluation run records the model/ruleset version, ranked predictions, abstention behavior, and whether the confirmed answer appeared at top-1 and top-3.
