# Applied Pharmacognosy Evidence Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provenance-first research evidence core for Riley Kirk/NAP/MoreBetter/Science of Smokability sources that can feed Grow Doc and related THC applications without mixing restricted human data or unreviewed claims into training.

**Architecture:** Extend the existing controlled source/RAG system with research-source, study, and research-claim schemas plus deterministic validation. Seed verified public metadata as RAG/reference-only records and publish only reviewed, scoped claims. Keep human participant data out of the repo and make all newly seeded facts weight-training-ineligible.

**Tech Stack:** JSON Schema 2020-12, Node.js validators, existing npm validation scripts, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-04-riley-kirk-applied-pharmacognosy-evidence-design.md`

## Global Constraints

- GitHub remains the canonical machine/code source; Drive remains the human/source-evidence store.
- Scientific factual claims are RAG/reference first and `weight_training_eligible=false`.
- A citation is not a data or asset license.
- Restricted/private participant-level data is metadata-only unless explicit access authorization is documented.
- Observational evidence must not be represented as causal.
- Non-cannabis research must remain explicitly transferable/non-cannabis.
- New research records must not enter protected held-out evaluation slices.
- Contribution claims and receipts must conform to repository rules.

## Review Focus

- Restricted/private dataset records must fail if marked redistributable or training eligible.
- Human-subject study records must fail if they contain direct identifiers or raw participant rows.
- Observational claims must fail when marked causal.
- Non-cannabis studies must fail when labeled cannabis-specific without an explicit cannabis specimen/population.
- Duplicate DOI/PMID/canonical-URL aliases must be detected before publication.

---

### Task 1: Register the evidence-core contribution task

**Files:**
- Modify: `contributions/tasks.json`
- Modify: `contributions/claims.json`

**Interfaces:**
- Produces: active `GD-SYS-002` task authorizing evidence-core schema/validator paths.
- Consumes: existing contribution registry contract.

- [ ] Add `GD-SYS-002` with allowed paths for `dataset/schema/research-*.schema.json`, `scripts/validate-research-evidence.mjs`, `scripts/test-research-evidence-validator.mjs`, `package.json`, and `docs/research-evidence/`.
- [ ] Claim the task on branch `work/grow-doc/GD-SYS-002/riley-kirk-20261004`.
- [ ] Run contribution validators through CI.
- [ ] Commit.

### Task 2: Add research evidence schemas and validator

**Files:**
- Create: `dataset/schema/research-source.schema.json`
- Create: `dataset/schema/research-study.schema.json`
- Create: `dataset/schema/research-claim.schema.json`
- Create: `scripts/test-research-evidence-validator.mjs`
- Create: `scripts/validate-research-evidence.mjs`
- Modify: `package.json`

**Interfaces:**
- Produces: deterministic validator for research source/study/claim bundles.
- Consumes: JSON documents conforming to the three schemas.

- [ ] Write failing validator tests covering restricted-data misuse, causal-overclaim from observational evidence, non-cannabis scope confusion, missing source binding, and duplicate identifiers.
- [ ] Verify RED in CI.
- [ ] Implement schemas and validator.
- [ ] Add `validate:research-evidence` npm script.
- [ ] Verify GREEN and existing source/contribution validation.
- [ ] Commit.

### Task 3: Seed Kirk/NAP/MoreBetter/Smokability source and study records

**Files:**
- Create: `dataset/registry/research-sources-kirk-nap-v1.json`
- Create: `dataset/reviewed/research-studies-kirk-nap-v1.json`
- Create: `docs/research-evidence/KIRK_NAP_SOURCE_NOTES.md`
- Modify: `contributions/tasks.json`
- Modify: `contributions/claims.json`

**Interfaces:**
- Produces: versioned verified metadata for public source families.
- Consumes: Task 2 schemas/validator.

- [ ] Release `GD-SYS-002`; claim `GD-RAG-001` on a compliant branch.
- [ ] Seed canonical metadata for Real Data Project, MoreBetter beverage study metadata, Science of Smokability Phase I and II project pages, the 2025 Phase I results article, 2026 CHS paper, and 2026 kratom RWE methodology paper.
- [ ] Mark MoreBetter participant-level data restricted/metadata-only and non-cannabis kratom study transferable only.
- [ ] Record exact DOI/PMID/URL identifiers and limitations.
- [ ] Validate records and contribution state.
- [ ] Commit.

### Task 4: Add reviewed RAG claims and application tags

**Files:**
- Create: `dataset/claims/research-claims-kirk-nap-v1.json`
- Update generated RAG/tool artifact only through existing deterministic builder if supported.

**Interfaces:**
- Produces: scoped, source-bound claims for retrieval.
- Consumes: source/study IDs from Task 3.

- [ ] Write claims only for facts directly supported by the verified primary/public sources.
- [ ] Assign evidence-design tier, scope, limitations, `rag_eligible=true`, `weight_training_eligible=false`.
- [ ] Add application targets: `grow_doc`, `encyclopedia`, `academy`, `terpene_atlas`, `dry_cure`, `beverage_education`, `breeder_journal` where justified.
- [ ] Run source-quality, semantic-leakage, and research-evidence validation.
- [ ] Commit.

### Task 5: Contribution receipt, full CI, and integration PR

**Files:**
- Create: `contributions/receipts/<contribution-id>.json`
- Update: `contributions/claims.json` to release final claim after integration decision.

**Interfaces:**
- Produces: auditable contribution record and PR.
- Consumes: exact changed paths, source IDs, validation results, base/head commits.

- [ ] Generate receipt with all source IDs and `training_eligible=false`, `weight_training_eligible=false`.
- [ ] Run `npm run check`, `npm test`, `npm run build`, `npm run validate:sources`, `npm run validate:grow-doc-contributions`, `npm run validate:model-source-evidence-quality`, `npm run validate:model-semantic-leakage`, and `npm run validate:research-evidence`.
- [ ] Inspect any failed CI job logs and fix root causes.
- [ ] Open PR with exact validation evidence and source/reuse summary.
