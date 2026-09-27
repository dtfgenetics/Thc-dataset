# GitHub Code Harvest — Grow Doc / Diagnostic Tooling — 2026-09-27

## Purpose

Use proven open-source patterns where they improve diagnostic transparency, image-intake quality, or maintainability without replacing Grow Doc's evidence-first three-pass contract.

## json-rules-engine

Repository: https://github.com/CacheControl/json-rules-engine  
Reviewed version: 7.3.2  
License: ISC.

Useful patterns:
- declarative rule conditions;
- event/rule separation;
- auditable fact inputs;
- deterministic rules testing.

Decision: **do not migrate Grow Doc's current differential engine.**

The canonical scorer already contains domain-specific safeguards that a generic engine would have to recreate:
- indicator-specific weighting based on discriminating frequency;
- contradiction penalties;
- growth-stage and evidence-slot context;
- root-zone chemistry and watering evidence requirements;
- history contribution;
- laboratory/microscopy confirmation boundaries;
- photo-only confidence caps;
- response-policy-specific confirmation requirements;
- close-margin confidence downgrading.

Replacing this with a generic engine would add abstraction without improving the current diagnostic contract.

### Action taken instead: differential evidence matrix

Added:
- `src/lib/differential-matrix.ts`
- `src/lib/differential-matrix.test.ts`

The result UI now displays the top candidates side-by-side with:
- confidence band;
- ranking score;
- supporting evidence count;
- contradictory evidence count;
- missing-evidence count;
- candidate-specific unobserved clues that can separate leading look-alikes.

The matrix explicitly says ranking scores are not probabilities and do not constitute laboratory confirmation.

## OpenCV.js reference

Project: https://github.com/opencv/opencv  
License: Apache-2.0.

High-value future uses:
- feature matching for repeat-photo alignment;
- geometric registration;
- more sophisticated blur/focus metrics;
- segmentation/measurement helpers after real validation.

Decision: do not load OpenCV.js in the initial Grow Doc shell. The WASM/runtime footprint is unnecessary for basic intake-quality checks.

### Action taken instead: local image quality preflight

Added:
- `src/lib/image-quality.ts`
- `src/lib/image-quality.test.ts`
- integration into `inspectEvidenceFile()`.

The browser now samples uploaded images locally and can flag:
- very dark images;
- over-bright images;
- clipped shadow detail;
- clipped highlight detail;
- unusually low edge detail consistent with soft/out-of-focus intake.

The preflight does not identify diseases or plants. It only helps the user submit evidence with enough visual information for later review.

## Keep as later research targets

### MediaPipe Tasks Vision
Repository family: Google MediaPipe  
License: Apache-2.0.

Use only when there is a validated cannabis-specific model or for low-risk image utilities such as embeddings, duplicate grouping, framing assistance, or image-quality support. Do not use a generic crop classifier as cannabis diagnostic ground truth.

### OpenCV.js
Revisit only for repeat-photo alignment, geometric comparison, or validated image measurements that cannot be implemented cleanly with Canvas.

### Generic rules engines
Revisit only if Grow Doc evolves into a much larger declarative rule authoring platform where domain editors need to modify conditions without TypeScript changes. Preserve all current confidence and confirmation boundaries if that transition ever occurs.


## Diagnostic image preprocessing — Cropper.js benchmark

### Cropper.js 2.2.0
Repository: https://github.com/fengyuanchen/cropperjs  
License: MIT.

Reviewed capabilities:
- movable/resizable crop selections;
- zoom;
- pan/translation;
- rotation;
- touch/pointer interaction;
- canvas export through the current v2 selection API.

Decision for this pass: **benchmark and adapt the interaction contract, do not add the npm dependency yet.**

Reason:
Grow Doc CI uses `npm ci`. Cropper.js 2.x publishes generated bundles from a multi-package `@cropper/*` workspace, so adding the dependency correctly requires a regenerated lockfile and full transitive dependency update. The current environment cannot safely regenerate that lock without risking an invalid CI state.

Action taken instead:
- added `src/components/ImageDetailEditor.tsx` using native browser Canvas;
- added zoom, pan, rotate and a 4:3 derived diagnostic detail view;
- retained the original `EvidenceFile.file` unchanged;
- added optional `analysisFile`, `analysisPreviewUrl` and transform metadata;
- visual-analysis requests now send the original image first and the derived symptom detail second;
- users can return to the original-only analysis path at any time;
- derived object URLs are explicitly revoked;
- mobile layout and Escape-to-close behavior are included;
- added deterministic source-contract validation and a unit test for original+derived media ordering.

Evidence boundary:
A crop is a derived observational aid. It is never treated as replacement ground truth, never overwrites the source upload, and never upgrades diagnostic certainty by itself.

Future dependency trigger:
Adopt Cropper.js directly when the package pipeline can regenerate and review `package-lock.json` cleanly, or if the native editor needs freeform crop handles/multi-selection beyond the current focused symptom-detail workflow.
