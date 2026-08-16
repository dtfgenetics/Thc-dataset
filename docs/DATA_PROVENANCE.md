# THC Plant Diagnostic — Data Provenance Contract

This document defines how diagnostic datasets, reference media, derived assets, and source records are traced across GitHub and the controlled Google Drive evidence system.

## Canonical ownership

- GitHub `dtfgenetics/Thc-dataset` owns machine-readable schemas, registries, manifests, normalized records, application data, tests, and build logic.
- Google Drive `03 Education/THC Plant Diagnostic Knowledge Base` owns controlled research/evidence packets, licensing correspondence, approved source assets, human review records, and the preserved dataset pipeline archive/control system.
- Google Drive `07 Websites & Apps/DTFSeeds Platform/04 Plant Diagnostic App` owns application planning and integration contracts.

## Required asset provenance

`dataset/schema/asset.schema.json` is the machine contract for acquired/reference media. An asset is not an approved reference or training item merely because a file exists.

Every accepted asset record must preserve the required schema fields, including:

- stable asset and dataset IDs;
- source URL and, where applicable, original URL/source file ID;
- storage lane;
- media type;
- creator/rights holder where known;
- license and required attribution;
- host species and host context;
- issue IDs and relevant organ/view/stage/severity context where known;
- evidence tier;
- confirmation method/status;
- review status;
- training eligibility and split when applicable;
- source-group relationship to prevent leakage/near-duplicate split contamination;
- cryptographic SHA-256;
- perceptual hash;
- display permission;
- explicit use limitations.

Unknown rights or display permission must remain unknown/restricted; they must not be silently upgraded to reusable/public/training-safe.

## Evidence and diagnosis rules

- A citation proving a biological claim does not automatically grant an image license.
- Text descriptions are not reference images.
- Visual similarity alone does not laboratory-confirm viroids, viruses, phytoplasmas, Spiroplasma, or other conditions that require confirmatory testing.
- User uploads are excluded from training unless a separate explicit rights/consent pathway records permission.
- `visual`, `expert-reviewed`, `measured-exposure`, `lab-confirmed`, and `illustrative` evidence are distinct confirmation states and must not be collapsed.
- Locked evaluation assets cannot be training eligible.

## Lifecycle

1. Acquire candidate/source record.
2. Record rights/source metadata before promotion.
3. Hash and assign source grouping.
4. Normalize/derive without overwriting the original.
5. Scientific review and licensing review remain separate gates.
6. Approve only to the permitted lane/use.
7. Assign dataset split only after grouping/dedup controls.
8. Retain rejected/restricted provenance records where useful for audit, without making the media publicly reusable.
9. Every public/app reference must be traceable back to the machine record and controlled evidence/source record.

## No-fabrication rule

Do not invent missing licenses, creators, confirmation methods, source URLs, laboratory confirmation, or review approval. Missing information stays missing and blocks any use that requires it.

## Release gate

Diagnostic releases must pass the repository checks/tests/build, the source-of-truth rules, and the DTF portfolio release criteria. A release record should identify the dataset/app version and the controlled evidence/register version used to support it.
