# Riley Kirk / Applied Pharmacognosy Evidence Architecture

Date: 2026-10-04  
Repository: `dtfgenetics/Thc-dataset`  
Status: design approved in chat; implementation pending plan review

## Goal

Extend the existing THC evidence/data architecture so research, datasets, methods, and tools discovered through Dr. Riley Kirk's work, the Network of Applied Pharmacognosy (NAP), MoreBetter, the Science of Smokability, and closely connected primary research can be reused across Grow Doc, the Encyclopedia, THC Academy, Terpene Atlas, Plant Atlas, Breeder Journal, post-harvest tools, beverage education, and future research dashboards without weakening provenance, licensing, privacy, or held-out evaluation boundaries.

## Why this belongs in the existing system

The repository already provides the correct foundation:

- versioned source registries and schemas;
- provenance and rights states;
- evidence tiers and confirmation states;
- RAG-first handling of scientific factual claims;
- training eligibility separated from reference/RAG eligibility;
- source-identity and leakage controls;
- machine-readable tool-data outputs;
- GitHub as canonical machine/code source and Drive as canonical human/source-evidence store.

This project extends those controls rather than creating a parallel "Kirk database."

## Scope

### In scope

1. Research-source registry for publications, datasets, study protocols, dashboards, public study pages, methods, and analytical tools.
2. Study/protocol metadata for observational, longitudinal, controlled, analytical, survey, and community-science work.
3. Claim/evidence records with exact source binding, scope, limitations, rights, and allowed uses.
4. Chemistry/metabolomics metadata for HPLC, LC-MS/MS, MS/MS molecular networking, NMR, spectral annotation, and MassQL-like querying.
5. Longitudinal observation models applicable to plants and, in a separately governed lane, human real-world evidence.
6. Post-harvest quality measurements including water activity, cure conditions, chemistry, smoke/sensory measurements, and outcome relationships.
7. Interfaces to existing genetics, phenotyping, diagnostic, cultivation, bioinformatics, and RAG layers.
8. A migration inventory describing what is reusable now, citation-only, restricted, or permission-dependent.

### Out of scope for the first implementation

- copying proprietary MoreBetter participant-level data;
- storing identifiable human health data in the cultivation/plant dataset;
- using observational human data as medical-diagnostic ground truth;
- promoting newly discovered scientific claims directly into model weights;
- ingesting media without asset-level rights review;
- presenting non-cannabis natural-product findings as cannabis-specific evidence.

## Source families to track

### 1. Dr. Riley Kirk credentials and research footprint

Track verified records for:

- pharmaceutical sciences / natural-product chemistry training;
- medicinal-plant chemistry and pharmacognosy;
- LC-MS/MS and molecular networking;
- natural-product isolation and bioassays;
- botanical authentication;
- cannabis chemistry and pharmacology;
- real-world evidence and longitudinal community research;
- harm-reduction / cannabinoid adverse-event work;
- science communication and public education.

Credential pages are identity/context sources. Scientific claims must resolve to the underlying publication, dataset, or study source whenever one exists.

### 2. Network of Applied Pharmacognosy

Track:

- Real Data Project / R-Dub / QuickLog study model;
- public dashboards and result pages;
- longitudinal cannabis-community studies;
- cannabis and sleep work;
- infused-beverage studies;
- dosing research/education;
- community-science protocols;
- published manuscripts and preprints;
- collaboration and data-access terms.

### 3. MoreBetter

Track methodology and public metadata for:

- longitudinal repeated-participant designs;
- study-instrument versioning;
- audit trails;
- scheduled/time-locked observations;
- real-world product, dose, route, purpose, and outcome capture;
- public publications and datasets;
- restricted/private datasets as metadata only unless access is explicitly granted.

### 4. Science of Smokability

Track the complete cultivation/post-harvest-to-product chain, including:

- cultivation practices;
- flower properties;
- water activity;
- drying and curing;
- ash characteristics;
- lightability/burn behavior;
- smoke composition;
- nitrosamines and other measured smoke chemistry where reported;
- cannabinoids and terpenes;
- sensory/community ratings;
- study phases, protocols, and published outcomes.

### 5. Natural-product analytical methods

Track primary literature associated with Kirk's research footprint where useful to our tools, including:

- LC-MS/MS metabolomics;
- MS/MS molecular networking;
- GNPS-style spectral networking;
- MassQL or equivalent mass-spectrometry query methods;
- HPLC;
- NMR;
- extraction/fractionation;
- compound isolation;
- permeability and bioactivity assays;
- natural-product screening libraries;
- botanical authentication / fingerprinting.

These methods may be reusable even when the studied organism is not cannabis, but the host/context must remain explicit.

## Canonical evidence graph

The system should model:

```
Source
  -> Study
    -> Dataset
      -> Subject / Specimen
        -> Observation
          -> Measurement
            -> Exposure / Intervention
              -> Outcome
                -> Claim
```

Additional relations:

```
Source -> Person / Organization
Study -> Protocol
Study -> Instrument
Dataset -> License / Access policy
Measurement -> Method
Claim -> Evidence tier
Claim -> Limitation
Claim -> Application targets
Specimen -> Genotype / cultivar / accession
Observation -> Environment
Product -> Chemistry profile
Product -> Formulation
Session -> Product + dose + route
```

## Separation of plant and human evidence

### Plant/cultivation lane

A plant can be followed longitudinally as:

```
seed_lot
-> genotype
-> plant_id
-> environment
-> cultivation_events
-> observations
-> diagnostic_events
-> interventions
-> responses
-> flowering
-> harvest
-> drying
-> curing
-> chemistry
-> sensory/quality
-> progeny/selection
```

### Human real-world-evidence lane

Human observations require separate governance:

```
study_subject_pseudonym
-> consent/version
-> product/formulation
-> chemistry when available
-> amount
-> route
-> session timestamp
-> intended purpose
-> onset
-> duration
-> reported effects
-> adverse effects
-> follow-up
```

Rules:

- no identifiable human health data in the plant dataset;
- no public exposure of participant-level records without explicit lawful authorization;
- human RWE remains observational evidence unless study design supports stronger inference;
- health/safety records must carry medical limitations and escalation language where applicable.

## Proposed source-record extensions

The existing source schema should be extended or complemented with research-source records containing:

- `source_id`
- `source_type` (paper, dataset, protocol, dashboard, registry, method, book, educational page)
- `title`
- `authors`
- `organizations`
- `publication_date`
- `doi`
- `pmid`
- `accession`
- `canonical_url`
- `retrieved_at`
- `content_sha256`
- `license`
- `access_state`
- `redistribution_state`
- `rag_eligible`
- `training_eligible`
- `human_subject_data`
- `study_design`
- `population_or_specimen`
- `domain_tags`
- `methods`
- `limitations`
- `provenance_status`
- `review_status`

## Proposed study/protocol record

Each study should support:

- study ID and source bindings;
- sponsor / organization;
- investigators;
- objective / research question;
- design;
- recruitment or specimen source;
- inclusion/exclusion criteria when published;
- sample size;
- repeated-measures flag;
- observation schedule;
- exposures/interventions;
- outcomes;
- instruments/questionnaires;
- analytical instruments/methods;
- statistical methods when published;
- ethics/IRB metadata when applicable;
- data-availability statement;
- dataset accession or access process;
- known limitations;
- cannabis-specific vs transferable status.

## Evidence tiers

Do not collapse current vision tiers. Add a research-claim tier system for literature and observational evidence.

Recommended hierarchy:

- `R0-systematic-review-guideline`
- `R1-controlled-causal`
- `R2-controlled-association`
- `R3-longitudinal-observational`
- `R4-cross-sectional-observational`
- `R5-case-series-survey`
- `R6-mechanistic-analytical`
- `R7-expert-education-context`
- `R8-community-anecdotal`

These tiers describe evidence design, not truth. Confirmation, replication, sample size, conflicts, and limitations remain separate fields.

## Rights and reuse lanes

Every discovered item must be assigned one lane before use:

1. **Reusable raw/open** — open license and verified provenance; raw redistribution/use allowed under stated terms.
2. **RAG/reference** — factual or methodological reuse with citation; raw content/assets not necessarily redistributable.
3. **Metadata-only/restricted** — existence and access process can be stored, but underlying dataset/content cannot be copied.
4. **Permission required** — potentially useful but must remain quarantined until rights/data-use permission is documented.
5. **Reject** — unverifiable provenance, incompatible rights, misleading scope, or unusable scientific quality.

A citation is not a data license. A paper's license does not automatically grant rights to every underlying participant dataset, supplementary asset, or third-party image.

## Initial verified source inventory

The first migration pass should seed records for the following source families, then resolve each to primary publications/datasets where available:

1. Vermont State University faculty profile for Riley Kirk — credential/context source.
2. Network of Applied Pharmacognosy About page — organization/person context.
3. NAP Real Data Project pages — project/protocol/public-results sources.
4. NAP public research/blog pages describing longitudinal cannabis, sleep, and beverage studies — discovery metadata pending primary-publication resolution.
5. MoreBetter public methodology/about material — platform/method metadata; proprietary data remains restricted.
6. Science of Smokability project page — protocol/project metadata; results must resolve to published study outputs when available.
7. 2026 Cannabinoid Hyperemesis Syndrome survey paper — published human observational evidence.
8. 2026 real-world Mitragyna speciosa dose/focus/energy paper — transferable longitudinal RWE methodology, not cannabis evidence.
9. Kirk-associated natural-product publications on:
   - LC-MS/MS-based botanical molecular networking/authentication;
   - cyanobacterial natural-product discovery;
   - polyphenol metabolite permeability/inflammation;
   - anti-MRSA natural-product screening;
   - related analytical-method publications discovered during bibliography resolution.

## Project-specific outputs

### Grow Doc

Use this architecture to improve:

- longitudinal case histories;
- pre/post intervention tracking;
- causal-vs-correlational language;
- evidence-backed diagnostic follow-up;
- post-harvest condition logging;
- RAG retrieval against reviewed research claims.

### Encyclopedia / THC Academy

Add:

- source-backed claim blocks;
- study-design labels;
- evidence-strength labels;
- "what the evidence actually shows" sections;
- method explainers for chromatography, MS, NMR, metabolomics, longitudinal studies, and observational evidence;
- explicit separation of controlled evidence, observational evidence, expert interpretation, and anecdote.

### Terpene Atlas / chemistry tools

Support:

- compound identity;
- analytical method;
- retention time where applicable;
- precursor/product ion metadata;
- spectral references;
- molecular-family/network relationships;
- concentration and uncertainty;
- sample preparation and instrument context;
- cultivar/product/specimen binding.

Do not infer human effects from terpene presence alone.

### Plant Atlas / Breeder Journal

Link:

- genotype;
- phenotype;
- environmental history;
- morphology;
- chemistry;
- selection decisions;
- progeny performance;
- repeated observations across generations.

### Dry/Cure tools

Add structured capture for:

- harvest state;
- temperature;
- RH;
- water activity;
- time;
- handling/container state;
- mass change;
- chemistry;
- visual/sensory observations;
- burn/smoke quality measurements when scientifically defined.

### Beverage education

Ingest published evidence concerning:

- formulation;
- cannabinoid content;
- dose;
- onset;
- duration;
- alcohol co-use where studied;
- reported outcomes;
- study limitations and population.

This remains education, not individualized medical advice.

## Ingestion workflow

1. Discover candidate source.
2. Resolve to primary source.
3. Capture canonical identifier and retrieval timestamp.
4. Determine rights/access state.
5. Hash retrieved content where local storage is permitted.
6. Extract study/method metadata.
7. Extract candidate claims with scope and limitations.
8. Human/review gate for scientific accuracy.
9. Publish approved facts to RAG/reference layer.
10. Keep weight-training eligibility false by default.
11. Generate application-specific derived data only from reviewed records.
12. Preserve exact source bindings through every derivative.

## Validation requirements

New validators should eventually enforce:

- every claim has at least one source;
- every source has an access/rights state;
- restricted human data cannot enter public artifacts;
- observational evidence cannot be labeled causal;
- non-cannabis work cannot silently become cannabis-specific;
- educational/web claims preserve source and limitations;
- content hashes match frozen source snapshots where stored;
- duplicate DOI/PMID/URL aliases resolve to one canonical source identity;
- generated RAG/tool data is deterministic;
- no new research source contaminates protected held-out evaluation slices.

## Success criteria

The migration is successful when:

1. Kirk/NAP/MoreBetter/SoS research is represented as structured, provenance-bound records rather than notes.
2. Every reusable scientific claim has a primary source and evidence-design label.
3. Restricted or proprietary data is represented without unauthorized copying.
4. Plant, chemistry, post-harvest, genetics, and human observational data can interoperate without sharing inappropriate fields.
5. Existing applications can consume reviewed records through generated tool/RAG data.
6. New sources can be added by the same intake workflow without schema reinvention.
7. The system remains compatible with the repository's current provenance, licensing, RAG-first, and held-out-evaluation controls.

## Implementation decomposition

This architectural change should be implemented in separate testable slices:

1. Research-source/study/claim schemas and validators.
2. Riley Kirk/NAP/MoreBetter/SoS seed registry.
3. Primary-publication and dataset resolver.
4. Reviewed claim extraction/RAG publishing.
5. Chemistry/metabolomics method records.
6. Longitudinal plant-observation extension.
7. Human-RWE governance and schemas.
8. Application adapters for Grow Doc, Encyclopedia/Academy, chemistry tools, breeder/plant systems, dry/cure, and beverages.

Each slice must preserve the existing source-of-truth and contribution rules.
