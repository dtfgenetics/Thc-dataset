import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const OBSERVATIONAL = new Set(['longitudinal_observational','cross_sectional_observational','survey','case_series'])
const NON_CANNABIS = new Set(['transferable_non_cannabis','general_method'])

function pushRequired(errors, obj, fields, label) {
  for (const field of fields) {
    if (!(field in obj)) errors.push(`${label}: missing required field ${field}`)
  }
}

function canonicalIdentifiers(source) {
  const ids = []
  if (source.doi) ids.push(`doi:${String(source.doi).trim().toLowerCase().replace('https://doi.org/','').replace('http://doi.org/','').replace('https://dx.doi.org/','').replace('http://dx.doi.org/','')}`)
  if (source.pmid) ids.push(`pmid:${String(source.pmid).trim().toLowerCase()}`)
  if (source.canonical_url) {
    try {
      const u = new URL(source.canonical_url)
      u.hash = ''
      if (u.pathname !== '/') u.pathname = u.pathname.replace(/\\/+$/,'')
      ids.push(`url:${u.toString().toLowerCase()}`)
    } catch {
      ids.push(`url-invalid:${String(source.canonical_url).trim().toLowerCase()}`)
    }
  }
  return ids
}

export function validateResearchEvidenceBundle(bundle) {
  const errors = []
  if (!bundle || typeof bundle !== 'object') return ['bundle must be an object']
  if (bundle.schema_version !== 'research-evidence-bundle-v1') errors.push('unsupported schema_version')
  for (const key of ['sources','studies','claims']) {
    if (!Array.isArray(bundle[key])) errors.push(`${key} must be an array`)
  }
  if (errors.length) return errors

  const sourceById = new Map()
  const studyById = new Map()
  const seenCanonical = new Map()

  for (const source of bundle.sources) {
    pushRequired(errors, source, ['source_id','source_type','title','canonical_url','access_state','redistribution_state','rag_eligible','training_eligible','human_subject_data','cannabis_scope'], 'source')
    if (!source.source_id) continue
    if (sourceById.has(source.source_id)) errors.push(`duplicate source_id: ${source.source_id}`)
    sourceById.set(source.source_id, source)

    if (source.access_state === 'restricted') {
      if (source.redistribution_state === 'open' || source.training_eligible === true) {
        errors.push(`${source.source_id}: restricted source cannot be redistributable or training eligible`)
      }
    }
    if (source.redistribution_state === 'metadata_only' && source.training_eligible === true) {
      errors.push(`${source.source_id}: metadata-only source cannot be training eligible`)
    }

    for (const identifier of canonicalIdentifiers(source)) {
      const prior = seenCanonical.get(identifier)
      if (prior && prior !== source.source_id) errors.push(`duplicate canonical identifier ${identifier}: ${prior} and ${source.source_id}`)
      else seenCanonical.set(identifier, source.source_id)
    }
  }

  for (const study of bundle.studies) {
    pushRequired(errors, study, ['study_id','source_ids','study_design','cannabis_scope','human_subject_data','participant_level_data_in_repo','causal_inference_allowed','population_or_specimen','outcomes','limitations'], 'study')
    if (!study.study_id) continue
    if (studyById.has(study.study_id)) errors.push(`duplicate study_id: ${study.study_id}`)
    studyById.set(study.study_id, study)

    for (const sid of study.source_ids || []) {
      if (!sourceById.has(sid)) errors.push(`${study.study_id}: unknown source_id ${sid}`)
    }
    if (study.human_subject_data && (study.participant_level_data_in_repo === true || study.direct_identifiers_present === true)) {
      errors.push(`${study.study_id}: participant-level human data or direct identifiers are not permitted in this repository evidence lane`)
    }
    if (OBSERVATIONAL.has(study.study_design) && study.causal_inference_allowed === true) {
      errors.push(`${study.study_id}: observational study cannot enable causal inference`)
    }
  }

  for (const claim of bundle.claims) {
    pushRequired(errors, claim, ['claim_id','source_ids','study_ids','text','evidence_tier','inference','cannabis_scope','rag_eligible','weight_training_eligible','application_targets','limitations'], 'claim')
    if (claim.weight_training_eligible !== false) errors.push(`${claim.claim_id || 'claim'}: research factual claims must be weight_training_eligible=false`)

    for (const sid of claim.source_ids || []) {
      if (!sourceById.has(sid)) errors.push(`${claim.claim_id}: unknown source_id ${sid}`)
    }
    const studies = []
    for (const studyId of claim.study_ids || []) {
      const study = studyById.get(studyId)
      if (!study) errors.push(`${claim.claim_id}: unknown study_id ${studyId}`)
      else studies.push(study)
    }

    if (claim.inference === 'causal' && studies.some(s => OBSERVATIONAL.has(s.study_design))) {
      errors.push(`${claim.claim_id}: observational study evidence cannot support a causal claim`)
    }

    if (claim.cannabis_scope === 'cannabis') {
      const linkedSources = (claim.source_ids || []).map(id => sourceById.get(id)).filter(Boolean)
      if ((studies.length || linkedSources.length) &&
          studies.every(s => NON_CANNABIS.has(s.cannabis_scope)) &&
          linkedSources.every(s => NON_CANNABIS.has(s.cannabis_scope))) {
        errors.push(`${claim.claim_id}: non-cannabis evidence cannot be silently promoted to a cannabis-specific claim`)
      }
    }
  }

  return errors
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'))
}

function collectArray(root, globPrefix, key) {
  if (!fs.existsSync(root)) return []
  return fs.readdirSync(root)
    .filter(name => name.startsWith(globPrefix) && name.endsWith('.json'))
    .sort()
    .flatMap(name => {
      const data = readJson(path.join(root, name))
      if (Array.isArray(data)) return data
      if (Array.isArray(data[key])) return data[key]
      return []
    })
}

export function loadRepositoryResearchEvidence(repoRoot) {
  return {
    schema_version: 'research-evidence-bundle-v1',
    sources: collectArray(path.join(repoRoot,'dataset','registry'), 'research-sources-', 'sources'),
    studies: collectArray(path.join(repoRoot,'dataset','reviewed'), 'research-studies-', 'studies'),
    claims: collectArray(path.join(repoRoot,'dataset','claims'), 'research-claims-', 'claims')
  }
}

function main() {
  const here = path.dirname(fileURLToPath(import.meta.url))
  const repoRoot = path.resolve(here, '..')
  const bundle = loadRepositoryResearchEvidence(repoRoot)
  const errors = validateResearchEvidenceBundle(bundle)
  const result = {ok: errors.length === 0, sources: bundle.sources.length, studies: bundle.studies.length, claims: bundle.claims.length, errors}
  console.log(JSON.stringify(result, null, 2))
  return errors.length ? 2 : 0
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main()
}
