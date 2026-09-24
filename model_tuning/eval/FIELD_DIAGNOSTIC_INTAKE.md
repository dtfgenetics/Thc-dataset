# Grow Doc Field Diagnostic Candidate Intake

Status: intake policy for future protected evaluation candidates. This file contains no benchmark cases, labels, media, or answer keys.

## Evidence-first intake

Do not create a field-diagnostic case until both the scientific evidence and the media provenance can be independently reviewed. A plausible symptom description is not enough.

For every proposed case, record before case construction:

- proposed case family and diagnostic target;
- primary scientific source identifier (DOI/PMID/stable institutional record where available);
- exact claim scope supported by that source;
- species and cultivar/population when reported;
- growth stage, environment, medium and treatment when reported;
- study design and sample size when reported;
- publication year and evidence tier;
- known applicability limits and plausible look-alikes;
- media origin, license/permission, original file SHA-256 and capture context;
- reviewer disposition: accept, revise, reject, or insufficient evidence.

## Hard rejection rules

Reject rather than promote a candidate when:

1. the diagnostic label is inferred from an unverified web image, forum post, vendor page, generated image, or unsourced symptom chart;
2. the source supports a different species/system and the transfer is presented as Cannabis-specific fact without direct evidence;
3. media ownership/license or original-byte provenance cannot be established;
4. the proposed answer requires unavailable pH, EC, root-zone, environmental, laboratory, microscopy, molecular or pest-identification evidence;
5. a single image cannot distinguish leading alternatives and the expected answer fails to preserve that ambiguity;
6. the case duplicates or closely paraphrases existing protected evaluation material;
7. the source is superseded, retracted, materially corrected, or contradicted without an adjudication record;
8. benchmark labels, adjudication notes, expected observations or equivalent paraphrases have entered training/supervision data.

## Separation of knowledge and behavior

Scientific facts belong primarily in versioned retrieval corpora with source metadata. SFT/QLoRA should target durable behavior: disciplined observation, differential construction, uncertainty, abstention, evidence reconciliation, citation use, and structured educational explanation.

A publication may therefore be present in the retrieval corpus while the benchmark-specific prompt, media-label binding, expected differential, expected observations, adjudication and scoring metadata remain protected and evaluation-only.

## Candidate tranche order

Build reviewed candidates in this order:

1. healthy controls and mechanically/environmentally damaged controls;
2. experimentally supported Cannabis nutrient-withholding/toxicity cases;
3. nutrient look-alikes and deliberately insufficient-information cases;
4. Cannabis pathogens with direct diagnostic evidence;
5. arthropod/pest injury and look-alikes;
6. environmental/root-zone stresses;
7. multi-stressor and temporal cases;
8. adversarial-retrieval and out-of-distribution cases.

Each tranche must include negative/ambiguous controls. Do not construct a benchmark that rewards always naming a disorder.

## Pre-freeze checks

Before any candidate can become frozen evaluation material, require schema validation, unique IDs, media SHA-256 verification, license/provenance review, source review, evidence-applicability review, duplicate/near-duplicate search against training and existing heldouts, semantic contamination review, slice-coverage reporting, and a human-readable adjudication record.

Do not use candidate performance to tune prompts, adapters, retrieval parameters, thresholds or model-soup weights once a case has been designated protected. Use a separate development set for iterative tuning.
