# THC Plant Diagnostic Backend Control Module

Version: **0.3.0**

This directory is the portable backend/control layer for the THC Plant Diagnostic project. It is intentionally separate from the Vite UI in `src/` and from raw media assets.

## Source of truth

The controlled research registry remains in Google Drive. The backend imports a validated snapshot of these tables before production use:

- Dataset_Registry
- Unified_Taxonomy
- Class_Map
- Gap_Register
- Evidence_Reference
- Hard_Differentials
- Intervention_Evidence
- Diagnostic_Response_Policy
- Solution_Ranking_Policy
- Expert_Escalation_Policy
- Optional_Context_Fields

Registry spreadsheet ID: `1-PK8twQQgFB60IbhKubVofEC4-6bqNoxgywW66S3q-k`

## Diagnostic contract

1. A usable image/video must receive a useful provisional analysis without requiring pH, EC, temperature, RH, medium, or other grow metadata.
2. Optional context is requested only when it has meaningful information gain for unresolved candidates.
3. Diagnosis is three-pass: visual candidates -> controlled evidence/hard differentials -> contradiction/open-set verification.
4. The response policy applies condition-specific confidence ceilings. HLVd, pathogen subtype, pH lockout, and similarly weak visual etiologies cannot be presented as visually confirmed.
5. Diagnostic evidence and corrective-action evidence are separate.
6. Multi-label/co-occurring problems are allowed when independently supported.
7. Original model results are immutable. Human review creates a new version/superseding analysis rather than overwriting history.
8. User uploads are excluded from future training unless the user separately opts in and the case meets verification/rights gates.

## Data products

Do not collapse these products:

- diagnostic knowledge/evidence index
- licensed public reference media
- training-eligible media
- locked evaluation/benchmark media
- consent-controlled CCCD cases

## Versioning

Released backend-control versions are immutable. Update `backend/CURRENT.json` when a newer version becomes the active implementation.
