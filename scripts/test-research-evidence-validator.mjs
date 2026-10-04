import assert from 'node:assert/strict'
import { validateResearchEvidenceBundle } from './validate-research-evidence.mjs'

const baseSource = {
  source_id: 'SRC-TEST-001',
  source_type: 'paper',
  title: 'Example paper',
  authors: ['Example Author'],
  organizations: ['Example Org'],
  publication_date: '2026-01-01',
  canonical_url: 'https://example.org/paper',
  retrieved_at: '2026-10-04',
  license: 'CC BY 4.0',
  access_state: 'open',
  redistribution_state: 'open',
  rag_eligible: true,
  training_eligible: false,
  human_subject_data: false,
  cannabis_scope: 'cannabis',
  domain_tags: ['cannabis'],
  provenance_status: 'VERIFIED',
  review_status: 'reviewed'
}

const baseStudy = {
  study_id: 'STUDY-TEST-001',
  source_ids: ['SRC-TEST-001'],
  title: 'Example study',
  study_design: 'longitudinal_observational',
  cannabis_scope: 'cannabis',
  human_subject_data: true,
  participant_level_data_in_repo: false,
  causal_inference_allowed: false,
  population_or_specimen: 'adult cannabis consumers',
  outcomes: ['self-reported effect'],
  limitations: ['observational design']
}

const baseClaim = {
  claim_id: 'CLAIM-TEST-001',
  source_ids: ['SRC-TEST-001'],
  study_ids: ['STUDY-TEST-001'],
  text: 'Participants reported an outcome during the observational study.',
  evidence_tier: 'R3-longitudinal-observational',
  inference: 'association',
  cannabis_scope: 'cannabis',
  rag_eligible: true,
  weight_training_eligible: false,
  application_targets: ['encyclopedia'],
  limitations: ['observational design']
}

function bundle(overrides = {}) {
  return {
    schema_version: 'research-evidence-bundle-v1',
    sources: [structuredClone(baseSource)],
    studies: [structuredClone(baseStudy)],
    claims: [structuredClone(baseClaim)],
    ...overrides
  }
}

assert.deepEqual(validateResearchEvidenceBundle(bundle()), [])

{
  const b = bundle()
  b.sources[0].access_state = 'restricted'
  b.sources[0].redistribution_state = 'open'
  b.sources[0].training_eligible = true
  const errors = validateResearchEvidenceBundle(b)
  assert(errors.some(x => x.includes('restricted source')))
}

{
  const b = bundle()
  b.claims[0].inference = 'causal'
  const errors = validateResearchEvidenceBundle(b)
  assert(errors.some(x => x.includes('observational study') && x.includes('causal')))
}

{
  const b = bundle()
  b.sources[0].cannabis_scope = 'transferable_non_cannabis'
  b.studies[0].cannabis_scope = 'transferable_non_cannabis'
  b.studies[0].population_or_specimen = 'Mitragyna speciosa consumers'
  b.claims[0].cannabis_scope = 'cannabis'
  const errors = validateResearchEvidenceBundle(b)
  assert(errors.some(x => x.includes('non-cannabis') && x.includes('cannabis-specific')))
}

{
  const b = bundle()
  b.claims[0].source_ids = ['SRC-MISSING']
  const errors = validateResearchEvidenceBundle(b)
  assert(errors.some(x => x.includes('unknown source_id')))
}

{
  const b = bundle()
  b.sources.push({...structuredClone(baseSource), source_id:'SRC-TEST-002'})
  const errors = validateResearchEvidenceBundle(b)
  assert(errors.some(x => x.includes('duplicate canonical identifier')))
}

{
  const b = bundle()
  b.studies[0].participant_level_data_in_repo = true
  b.studies[0].direct_identifiers_present = true
  const errors = validateResearchEvidenceBundle(b)
  assert(errors.some(x => x.includes('participant-level human data')))
}

console.log('Research evidence validator tests: PASS')
