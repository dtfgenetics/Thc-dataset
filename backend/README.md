# THC Plant Diagnostic Backend Control Module

Current release: **v1.1.0** (`CODE-011`)

This directory is the portable backend/control layer for the THC Plant Diagnostic project. The public Git repository stores pull-ready code, schemas, policies and safe metadata snapshots. Large raw datasets, consent-controlled CCCD media, restricted archives and credentials stay outside the public repository.

## Current release

The tested immutable v1.1 package is stored in the controlled Drive release folder and is referenced by `backend/CURRENT.json`.

- Version: `1.1.0`
- Release ID: `CODE-011`
- SHA-256: `e4d78664ddd858e92386529a5f0a082607bef16b39d8cda16c8442e85ddf2fc1`
- Drive release file ID: `1bnx3EW3X_51krjE1XH2OqT1JESL6UOt9`

v1.1 includes the production-oriented v1.0 runtime plus controlled coverage/readiness scoring and targeted collection-priority routing.

## Source of truth

The authoritative editable research/control system remains in Google Drive. GitHub contains versioned reusable snapshots and code, not the only copy of the research registry.

Registry spreadsheet ID: `1-PK8twQQgFB60IbhKubVofEC4-6bqNoxgywW66S3q-k`

Key controlled tables include:

- Dataset_Registry
- Unified_Taxonomy
- Class_Map
- Gap_Register
- Evidence_Reference
- Coverage_Matrix
- Collection_Campaigns
- Active_Learning_Rules
- Hard_Differentials
- Intervention_Evidence
- Diagnostic_Response_Policy
- Solution_Ranking_Policy
- Expert_Escalation_Policy
- Optional_Context_Fields
- Benchmark_Plan
- Code_Release_Index

## Diagnostic contract

1. A usable image/video receives a useful provisional analysis without requiring pH, EC, temperature, RH, medium or other grow metadata.
2. Optional context is requested only when it has meaningful information gain for unresolved candidates.
3. Diagnosis is three-pass: visual candidates -> controlled evidence/hard differentials -> contradiction/open-set verification.
4. Response policies apply condition-specific confidence ceilings. HLVd, pathogen subtype, pH lockout and similarly weak visual etiologies cannot be presented as visually confirmed.
5. Diagnostic evidence and corrective-action evidence are separate.
6. Multi-label/co-occurring problems are allowed when independently supported.
7. Original model results are immutable. Human review creates a new/superseding analysis rather than overwriting history.
8. User uploads are excluded from future training unless the user separately opts in and verification/rights gates pass.
9. Locked benchmark assets never enter training, tuning or model selection.
10. Coverage/readiness state is advisory and cannot promote a weak or reference-only source into trusted ground truth.

## Data products

Do not collapse these products:

- diagnostic knowledge/evidence index
- licensed public reference media
- training-eligible media
- locked evaluation/benchmark media
- consent-controlled CCCD cases
- restricted/noncommercial source partitions

## Public Git safety

Do not commit:

- private user submissions or CCCD originals;
- API keys, database passwords, S3/R2 credentials or access tokens;
- third-party raw archives unless redistribution is explicitly permitted;
- restricted/noncommercial assets into a public-open release lane;
- benchmark media after it has been exposed to training.

## Versioning

Released backend-control versions are immutable. New work receives a new version. `backend/CURRENT.json` identifies the active tested release while the controlled Drive `Code_Release_Index` preserves the release history.
