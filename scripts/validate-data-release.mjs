import fs from 'node:fs/promises'
import path from 'node:path'

const root = process.cwd()
const requiredFiles = [
  // Curated release layer
  'data/manifest.json',
  'data/diagnostic-index.json',
  'data/diagnostic-index.csv',
  'data/reference-media.json',
  'data/reference-annotations.jsonl',
  'data/image-annotation-schema.json',
  'data/split-policy.json',
  'data/release-readiness.json',
  'data/public-dataset-registry.json',
  // Deterministically generated detailed layer
  'data/export-manifest.json',
  'data/diagnostic-profiles.json',
  'data/diagnostic-profiles.jsonl',
  'data/diagnostic-profiles.csv',
  'data/profiles/index.json',
  'data/sources.json',
  'data/profile-reference-media.json',
  'data/training-eligible-media.json',
]

const errors = []

async function existsNonEmpty(file) {
  try {
    const stat = await fs.stat(path.join(root, file))
    return stat.isFile() && stat.size > 0
  } catch {
    return false
  }
}

for (const file of requiredFiles) {
  if (!(await existsNonEmpty(file))) errors.push(`${file}: missing or empty`)
}

function parseJson(file) {
  return fs.readFile(path.join(root, file), 'utf8').then((text) => JSON.parse(text))
}

function duplicates(values) {
  return [...new Set(values.filter((value, i) => values.indexOf(value) !== i))]
}

function sorted(values) {
  return [...values].sort((a, b) => String(a).localeCompare(String(b)))
}

function sameJson(a, b) {
  return JSON.stringify(a) === JSON.stringify(b)
}

// Stop here with a useful file list instead of throwing confusing ENOENT errors.
if (errors.length) {
  console.error(`DATA RELEASE VALIDATION FAILED (${errors.length})`)
  for (const error of errors) console.error(`- ${error}`)
  process.exit(1)
}

const [
  curatedManifest,
  index,
  curatedMedia,
  readiness,
  publicRegistry,
  exportManifest,
  profiles,
  profileIndex,
  sources,
  profileReferenceMedia,
  trainingEligibleMedia,
] = await Promise.all([
  parseJson('data/manifest.json'),
  parseJson('data/diagnostic-index.json'),
  parseJson('data/reference-media.json'),
  parseJson('data/release-readiness.json'),
  parseJson('data/public-dataset-registry.json'),
  parseJson('data/export-manifest.json'),
  parseJson('data/diagnostic-profiles.json'),
  parseJson('data/profiles/index.json'),
  parseJson('data/sources.json'),
  parseJson('data/profile-reference-media.json'),
  parseJson('data/training-eligible-media.json'),
])

if (!Array.isArray(index.records) || index.records.length < 35) errors.push('diagnostic-index.json: expected at least 35 records')
if (!Array.isArray(curatedMedia.records) || curatedMedia.records.length < 21) errors.push('reference-media.json: expected at least 21 curated records')
if (!Array.isArray(readiness.classes) || readiness.classes.length !== index.records.length) errors.push('release-readiness.json: class coverage must match diagnostic index')
if (!Array.isArray(publicRegistry.datasets) || publicRegistry.datasets.length < 3) errors.push('public-dataset-registry.json: expected at least 3 verified transfer datasets')
if (!Array.isArray(profiles)) errors.push('diagnostic-profiles.json: top level must be an array')
if (!Array.isArray(profileIndex.records)) errors.push('data/profiles/index.json: records must be an array')
if (!Array.isArray(sources)) errors.push('sources.json: top level must be an array')
if (!Array.isArray(profileReferenceMedia)) errors.push('profile-reference-media.json: top level must be an array')
if (!Array.isArray(trainingEligibleMedia)) errors.push('training-eligible-media.json: top level must be an array')

if (!errors.length) {
  const indexIds = index.records.map((r) => r.id)
  const profileIds = profiles.map((r) => r.id)
  const profileSlugs = profiles.map((r) => r.slug)
  const profileIndexIds = profileIndex.records.map((r) => r.id)

  const duplicateIndexIds = duplicates(indexIds)
  const duplicateProfileIds = duplicates(profileIds)
  const duplicateSlugs = duplicates(profileSlugs)
  if (duplicateIndexIds.length) errors.push(`diagnostic-index.json: duplicate ids ${duplicateIndexIds.join(', ')}`)
  if (duplicateProfileIds.length) errors.push(`diagnostic-profiles.json: duplicate ids ${duplicateProfileIds.join(', ')}`)
  if (duplicateSlugs.length) errors.push(`diagnostic-profiles.json: duplicate slugs ${duplicateSlugs.join(', ')}`)

  if (!sameJson(sorted(indexIds), sorted(profileIds))) {
    errors.push('diagnostic-profiles.json: exported profile IDs do not exactly match diagnostic-index.json')
  }
  if (!sameJson(sorted(profileIds), sorted(profileIndexIds))) {
    errors.push('data/profiles/index.json: IDs do not exactly match diagnostic-profiles.json')
  }
  if (profileIndex.recordCount !== profiles.length) {
    errors.push(`data/profiles/index.json: recordCount ${profileIndex.recordCount} does not match ${profiles.length} profiles`)
  }

  const readinessIds = new Set(readiness.classes.map((r) => r.id))
  for (const id of indexIds) if (!readinessIds.has(id)) errors.push(`release-readiness.json: missing class ${id}`)

  const requiredProfileArrays = [
    'affectedParts','stages','indicators','exclusions','progression','lookAlikes',
    'confirmation','immediateActions','correctivePlan','prevention','warnings','sources','media',
  ]
  const profileById = new Map(profiles.map((profile) => [profile.id, profile]))

  for (const profile of profiles) {
    for (const field of ['id','slug','name','category','severity','reviewStatus','summary']) {
      if (profile[field] == null || profile[field] === '') errors.push(`${profile.id || '<missing-id>'}: missing ${field}`)
    }
    for (const field of requiredProfileArrays) {
      if (!Array.isArray(profile[field])) errors.push(`${profile.id}: ${field} must be an array`)
    }

    const file = `data/profiles/${profile.id}.json`
    if (!(await existsNonEmpty(file))) {
      errors.push(`${file}: missing or empty`)
      continue
    }
    try {
      const standalone = await parseJson(file)
      if (!sameJson(standalone, profile)) errors.push(`${file}: does not exactly match master diagnostic-profiles.json record`)
    } catch (error) {
      errors.push(`${file}: invalid JSON (${error.message})`)
    }
  }

  for (const entry of profileIndex.records) {
    const profile = profileById.get(entry.id)
    if (!profile) continue
    if (entry.path !== `data/profiles/${entry.id}.json`) errors.push(`${entry.id}: incorrect standalone profile path`)
    if (entry.sourceCount !== profile.sources.length) errors.push(`${entry.id}: sourceCount mismatch`)
    if (entry.mediaCount !== profile.media.length) errors.push(`${entry.id}: mediaCount mismatch`)
  }

  const jsonlText = await fs.readFile(path.join(root, 'data/diagnostic-profiles.jsonl'), 'utf8')
  const jsonlLines = jsonlText.split(/\r?\n/).filter(Boolean)
  const jsonlProfiles = []
  for (let i = 0; i < jsonlLines.length; i++) {
    try { jsonlProfiles.push(JSON.parse(jsonlLines[i])) }
    catch (error) { errors.push(`diagnostic-profiles.jsonl line ${i + 1}: invalid JSON (${error.message})`) }
  }
  if (jsonlProfiles.length !== profiles.length) errors.push('diagnostic-profiles.jsonl: record count does not match diagnostic-profiles.json')
  if (!sameJson(sorted(jsonlProfiles.map((r) => r.id)), sorted(profileIds))) errors.push('diagnostic-profiles.jsonl: IDs do not match master profile set')

  const sourceKeys = sources.map((r) => r.sourceKey)
  const duplicateSourceKeys = duplicates(sourceKeys)
  if (duplicateSourceKeys.length) errors.push(`sources.json: duplicate source keys ${duplicateSourceKeys.join(', ')}`)
  for (const source of sources) {
    if (!source.sourceKey || !source.title || !source.url) errors.push(`sources.json: incomplete source ${source.sourceKey || '<missing-key>'}`)
  }

  const generatedMediaIds = profileReferenceMedia.map((r) => r.id)
  const duplicateGeneratedMediaIds = duplicates(generatedMediaIds)
  if (duplicateGeneratedMediaIds.length) errors.push(`profile-reference-media.json: duplicate media ids ${duplicateGeneratedMediaIds.join(', ')}`)
  for (const row of trainingEligibleMedia) {
    if (row.trainingEligible !== true || row.trainingPermission !== 'permitted') {
      errors.push(`${row.id}: training-eligible media violates permission gate`)
    }
    if (!generatedMediaIds.includes(row.id)) errors.push(`${row.id}: training-eligible media missing from profile-reference-media.json`)
  }

  if (exportManifest.schemaVersion !== '2.0.0') errors.push('export-manifest.json: expected schemaVersion 2.0.0')
  if (exportManifest.deterministic !== true) errors.push('export-manifest.json: deterministic must be true')
  if (exportManifest.counts?.diagnosticProfiles !== profiles.length) errors.push('export-manifest.json: diagnostic profile count mismatch')
  if (exportManifest.counts?.sources !== sources.length) errors.push('export-manifest.json: source count mismatch')
  if (exportManifest.counts?.profileReferenceMedia !== profileReferenceMedia.length) errors.push('export-manifest.json: profile media count mismatch')
  if (exportManifest.counts?.trainingEligibleMedia !== trainingEligibleMedia.length) errors.push('export-manifest.json: training eligible count mismatch')

  if (curatedManifest.diagnosticProfileCount !== index.records.length) errors.push('manifest.json: diagnosticProfileCount does not match index')

  const annotationText = await fs.readFile(path.join(root, 'data/reference-annotations.jsonl'), 'utf8')
  const annotationLines = annotationText.split(/\r?\n/).filter(Boolean)
  const annotations = []
  for (let i = 0; i < annotationLines.length; i++) {
    try { annotations.push(JSON.parse(annotationLines[i])) }
    catch (error) { errors.push(`reference-annotations.jsonl line ${i + 1}: invalid JSON (${error.message})`) }
  }

  const curatedMediaIds = new Set(curatedMedia.records.map((r) => r.id))
  for (const row of annotations) {
    if (!curatedMediaIds.has(row.assetId)) errors.push(`reference-annotations.jsonl: unknown assetId ${row.assetId}`)
    if (row.trainingEligible === true) {
      if (row.rights?.trainingPermission !== 'permitted') errors.push(`${row.sampleId}: trainingEligible but training permission is not permitted`)
      if (!['train','validation','test'].includes(row.splitStatus)) errors.push(`${row.sampleId}: trainingEligible but no model split assigned`)
    }
  }

  if (curatedManifest.referenceMediaRecordCount !== curatedMedia.records.length) errors.push('manifest.json: referenceMediaRecordCount mismatch')
  if (curatedManifest.referenceAnnotationCount !== annotations.length) errors.push('manifest.json: referenceAnnotationCount mismatch')
}

if (errors.length) {
  console.error(`DATA RELEASE VALIDATION FAILED (${errors.length})`)
  for (const error of errors) console.error(`- ${error}`)
  process.exit(1)
}

console.log(JSON.stringify({
  ok: true,
  diagnosticProfiles: profiles.length,
  standaloneProfileFiles: profileIndex.records.length,
  uniqueSources: sources.length,
  generatedProfileMedia: profileReferenceMedia.length,
  trainingEligibleGeneratedMedia: trainingEligibleMedia.length,
  curatedReferenceMedia: curatedMedia.records.length,
  curatedReferenceAnnotations: curatedManifest.referenceAnnotationCount,
  transferDatasets: publicRegistry.datasets.length,
}, null, 2))
