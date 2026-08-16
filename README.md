# THC Grow Doc

Production-oriented React/Vite frontend for the plant-health evidence tool at `https://dtfseeds.com/thc-grow-doc/`.

## What is implemented

- Neutral diagnostic start state with no diagnosis before evidence.
- Multi-view image and optional video intake.
- Browser-side file-resolution and crop checks.
- Structured grow context and symptom intake.
- Ranked rule-based differentials with evidence for, evidence against, missing evidence, and confidence bands.
- Corrected condition taxonomy, complete issue-detail screens, licensing-aware reference library, dataset coverage dashboard, and local grow log.
- `/thc-grow-doc/` Vite base path for WordPress deployment.

This version does **not** claim to run a validated pixel-classification model. Uploaded media is previewed and quality-checked locally; structured symptoms and grow context drive the current differential ranking.

## Local development

```bash
npm install
npm run dev
```

Validation:

```bash
npm run check
npm test
npm run build
```

## Deployment

`npm run build` creates `dist/`. Publish the files inside `dist/` to the WordPress path serving `/thc-grow-doc/`, preserving the `assets/` directory.

Do not place the future reference-media collection in the JavaScript bundle or WordPress media library. Store approved originals in object storage, return responsive derivatives through a CDN, and keep metadata in a versioned database/API.

## Data rules

- A source citation is not an image license.
- Text descriptions do not count as reference images.
- Every approved image requires source, creator, license, issue, view, stage/severity where known, confirmation status, and review status.
- User uploads are excluded from training by default.
- Viroid, virus, phytoplasma, and Spiroplasma records must state that visual evidence cannot confirm infection.

## Source of truth

This repository is the canonical machine-readable/code source for the THC Plant Diagnostic system. Human-readable research, licensing, controlled registries, and approved source assets are maintained in the Google Drive master source.

See [`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md) for the canonical Drive/GitHub ownership rules and consolidation structure.
