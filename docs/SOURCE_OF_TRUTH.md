# THC Plant Diagnostic — Source of Truth

Last consolidated: 2026-08-15

## Purpose

This repository is the canonical machine-readable and application source for the THC Plant Diagnostic system.

## Canonical ownership

### GitHub — machine/code source

Repository: `dtfgenetics/Thc-dataset`

GitHub owns:

- application source code
- schemas and machine-readable diagnostic data
- versioned dataset releases
- backend/API code
- validation and tests
- build/deployment configuration
- scripts and data-processing logic

Do not store the only authoritative copy of a dataset schema, application rule, or executable pipeline in chat history, Base44, Figma, or a website builder.

### Google Drive — human/source evidence

Master source root:

`DTF Project Asset Library - MASTER SOURCE`

Canonical diagnostic knowledge folder:

`03 Education/THC Plant Diagnostic Knowledge Base`

Canonical application planning folder:

`07 Websites & Apps/DTFSeeds Platform/04 Plant Diagnostic App`

Drive owns:

- source research and evidence packets
- licensing and author permission records
- controlled dataset registries
- reference-image provenance and approval records
- annotation/adjudication standards
- human-readable project controls
- approved visual source assets

## Canonical diagnostic Drive structure

```text
03 Education/
└── THC Plant Diagnostic Knowledge Base/
    ├── 00 Governance & Standards/
    ├── 01 Diagnostic Profiles/
    ├── 02 Reference Images/
    ├── 03 Dataset Registries/
    ├── 04 Evidence & Licensing/
    ├── 05 Dataset Pipeline/
    └── 99 Archive/
```

The existing dataset pipeline was moved intact into `05 Dataset Pipeline` so its internal folders and file IDs remain stable.

## DTFSeeds application structure

```text
07 Websites & Apps/
└── DTFSeeds Platform/
    ├── 00 Control/
    ├── 01 Production Site/
    ├── 02 Game Hub/
    ├── 03 THC Education Site/
    ├── 04 Plant Diagnostic App/
    ├── 05 External App Integrations/
    └── 99 Archive/
```

## Tool rules

1. Codex and coding agents should treat this GitHub repository as the canonical code/data workspace.
2. Human research, licenses, source evidence, and approved originals belong in the master Drive structure.
3. Figma and image-generation tools are production surfaces, not archives; approved exports return to Drive.
4. Base44 and other hosted builders are prototypes/deployments, not the only source of project truth.
5. ChatGPT Library/project folders are working spaces only; final approved artifacts must be filed in Drive or GitHub.
6. Do not duplicate large reference-image collections into the application bundle. Store media externally and keep versioned metadata/API references in GitHub.
7. Never delete or supersede controlled source material during consolidation without first recording the replacement and archive location.

## Current consolidation status

Completed in the first consolidation pass:

- created the canonical diagnostic knowledge-base folder
- created governance, profile, image, registry, evidence/licensing, pipeline, and archive areas
- moved the existing diagnostic dataset pipeline intact into the canonical knowledge base
- moved the controlled public dataset registry into `03 Dataset Registries`
- moved loose annotation/adjudication, metadata README, and license-request documents out of Drive root into canonical diagnostic folders
- created the canonical DTFSeeds Platform application hierarchy

Next consolidation work should map remaining diagnostic Drive files to these folders, compare duplicates by ID/hash/version, and only then archive superseded copies.
