# Grow Doc diagnostic context and concept audit

Audited base: `2b54f54c91247f3761c8d993daf525c7f1e12d0a`. This is a repository audit, not a production deployment attestation or a claim that every possible defect has been found.

## Findings and closure criteria

| Priority | Finding | Evidence | Action / closure criterion |
| --- | --- | --- | --- |
| P1 | Malformed successful visual-service responses silently become empty observations | `requestVisualObservations` formerly swallowed JSON failures and accepted missing required fields | Fixed in this batch: reject incomplete envelopes, including missing boolean scope flags. Provider proxy also validates the envelope. Regression tests cover null, arrays, empty objects and wrong field types. |
| P1 | Uncertain/out-of-scope output can still contribute suggested symptom matches | Client and PHP proxy formerly retained `matchedIndicators` when `unknownOrOutOfScope=true` | Fixed in this batch: preserve descriptive notes and next views but clear symptom matches. Manual observations remain available. |
| P2 | Whitespace can prevent vocabulary matches and leave apparent duplicates | Client filtered trimmed strings but returned untrimmed entries; proxy trims its vocabulary | Fixed in this batch: normalize before deduplication and normalize returned matches. |
| P1 | Uploaded-media changes can leave an old visual result available | `VisualObservationReview` stores results independently of its evidence props | Open: bind results to an evidence fingerprint; invalidate old approvals/results and ignore in-flight responses when that fingerprint changes. Add an interaction test that replaces evidence during a request. |
| P1 | Video decoding and service requests have no client time limit | `waitForEvent` and `fetch` in `src/lib/visual-observations.ts` | Open: bounded metadata/seek waits and request cancellation; test a video that never emits readiness and a provider that never returns. Preserve recovery and object-URL cleanup. |
| P1 | The vision dataset is not ready for supervised diagnosis training | `data/model-training-readiness.json`: 0 eligible samples; 66 crops in the admission queue | Open: acquire rights-cleared, plant-linked samples with appropriate confirmation, controls and group-isolated splits. Reference count is not training readiness. |
| P1 | Reference evaluation lacks controls and locked samples | `data/evaluation-reference-coverage.json`: 21 annotations, 0 healthy controls, 1 look-alike binding, 0 locked-evaluation-eligible; 14 of 15 represented profiles below source-group target | Open: add confirmed healthy and confounder samples and freeze an independent evaluation set before reporting measured diagnostic performance. |
| P1 | Source-group diversity may be overstated | Reference annotations use figure-specific IDs such as `cockson-2019-figure-2` and `llewellyn-2023-figure-5` | Investigate before relabeling: audit publication, experiment, plant and capture relationships. Different figures from the same experiment are not automatically independent sources. Do not rewrite IDs without a migration and leakage audit. |
| P2 | Video coverage is effectively absent for Cannabis | 67 profile media references contain one video, a rights-unresolved soybean Dectes reference | Open: licensed Cannabis videos linked to observed plants, capture times and confirmation. Do not count a cross-crop reference as Cannabis progression evidence. |
| P2 | Coverage remains uneven | 61 profiles include 12 nutrient deficiencies and 11 fungal pathogens, but only 1 genetic/developmental, 1 virus, 1 viroid, 1 nematode and 2 environmental-stress profiles | Open: prioritize a sourced coverage matrix and common confounders; raw category counts do not prove diagnostic completeness. |
| P2 | Source date completeness is limited | 35 of 177 exported sources lack `publicationDate` | Open: verify dates on original institutional/publisher pages; retain explicitly unknown dates rather than guessing. Access dates and publication dates serve different purposes. |
| P2 | Completion status is narrower and older than its wording suggests | `model_tuning/project_completion_v1.json` audits `d8162a4...` and labels engineering complete while listing external blockers | Open: re-audit each completion claim against current evidence; report the audited revision and separate code readiness, data readiness, benchmark execution and deployment. |
| P2 | Production provenance and external controls remain unverified by this audit | Completion register lists branch protection, compute and FTP/provenance blockers | Revalidate through their authorized interfaces. Stored blocker notes are historical evidence, not a fresh check. This batch does not claim a live deployment. |
| P2 | Build performance needs measurement | Production build warns about a JavaScript chunk larger than 500 kB | Open: measure mobile loading and interaction cost before splitting code; compare before/after runtime and accessibility results. |

## Shared concepts

| Concept | Meaning | Evidence needed |
| --- | --- | --- |
| Observation | What is visible: plant part, leaf age, color, shape, distribution and capture quality | Original media and its capture context; uncertainty remains explicit |
| Context | Cultivar, stage, plant/leaf IDs, dates, production system, exposure and measurement method | Linked records; missing values remain unknown |
| Differential | Competing explanations ranked from observations and context | Supporting, contradicting and missing evidence for each candidate |
| Confirmation | Evidence supporting the specific causal or organism claim | Diagnosis-appropriate analytical, organism, molecular or controlled evidence linked to the plant |
| Progression | Changes in the same identified plant or comparable documented cohort | Capture times, stable identifiers and consistent views; three frames from one short clip do not establish a disease timeline |
| Confidence | Strength of evidence for the current case | Explicit basis and limitations; heuristic score margins and photo ceilings are not measured probabilities |
| Reference permission | Whether a particular asset may be displayed or reused | Item-level rights and attribution; permission does not confirm its diagnosis |
| Training admission | Whether a sample may enter a specified supervised split | Rights, annotation, confirmation, grouping, review and leakage controls; agent review must not be recorded as human or laboratory review |
| Release completion | A bounded result at an exact revision | Code checks, dataset checks, runtime verification and deployment provenance reported separately |

## Next bounded work

1. Bind visual observations and approvals to the current evidence set; add cancellation and bounded media waits.
2. Audit experiment/source grouping and establish independent controls before expanding claims of model performance.
3. Expand plant-linked, reusable Cannabis references and diagnostic video in the weakest categories.
4. Revalidate completion and production blocker records, then measure visitor-facing mobile performance.

Concurrent PR #518 addresses missing-visual guide discovery; this batch does not duplicate its UI work. No canonical diagnostic labels, rights, training eligibility, source-group IDs or model-readiness gates are changed here.
