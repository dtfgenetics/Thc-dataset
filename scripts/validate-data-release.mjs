import fs from 'node:fs/promises'
import path from 'node:path'

const root = process.cwd()
const requiredFiles = [
  'data/manifest.json',
  'data/diagnostic-index.json',
  'data/diagnostic-index.csv',
  'data/reference-media.json',
  'data/reference-annotations.jsonl',
  'data/image-annotation-schema.json',
  'data/split-policy.json',
  'data/release-readiness.json',
  'data/public-dataset-registry.json',
]

const errors = []
for (const file of requiredFiles) {
  try {
    const stat = await fs.stat(path.join(root, file))
    if (!stat.isFile() || stat.size === 0) errors.push(`${file}: missing or empty`)
  } catch {
    errors.push(`${file}: missing`)
  }
}

function parseJson(file) {
  return fs.readFile(path.join(root, file), 'utf8').then((text) => JSON.parse(text))
}

const [index, media, readiness, publicRegistry] = await Promise.all([
  parseJson('data/diagnostic-index.json'),
  parseJson('data/reference-media.json'),
  parseJson('data/release-readiness.json'),
  parseJson('data/public-dataset-registry.json'),
])

if (!Array.isArray(index.records) || index.records.length < 35) errors.push('diagnostic-index.json: expected at least 35 records')
if (!Array.isArray(media.records) || media.records.length < 21) errors.push('reference-media.json: expected at least 21 records')
if (!Array.isArray(readiness.classes) || readiness.classes.length !== index.records.length) errors.push('release-readiness.json: class coverage must match diagnostic index')
if (!Array.isArray(publicRegistry.datasets) || publicRegistry.datasets.length < 3) errors.push('public-dataset-registry.json: expected verified transfer datasets')

const ids = index.records.map((r) => r.id)
const duplicateIds = ids.filter((id, i) => ids.indexOf(id) !== i)
if (duplicateIds.length) errors.push(`diagnostic-index.json: duplicate ids ${[...new Set(duplicateIds)].join(', ')}`)

const readinessIds = new Set(readiness.classes.map((r) => r.id))
for (const id of ids) if (!readinessIds.has(id)) errors.push(`release-readiness.json: missing class ${id}`)

const annotationText = await fs.readFile(path.join(root, 'data/reference-annotations.jsonl'), 'utf8')
const annotationLines = annotationText.split(/\r?\n/).filter(Boolean)
const annotations = []
for (let i = 0; i < annotationLines.length; i++) {
  try { annotations.push(JSON.parse(annotationLines[i])) }
  catch (error) { errors.push(`reference-annotations.jsonl line ${i + 1}: invalid JSON (${error.message})`) }
}

const mediaIds = new Set(media.records.map((r) => r.id))
for (const row of annotations) {
  if (!mediaIds.has(row.assetId)) errors.push(`reference-annotations.jsonl: unknown assetId ${row.assetId}`)
  if (row.trainingEligible === true) {
    if (row.rights?.trainingPermission !== 'permitted') errors.push(`${row.sampleId}: trainingEligible but training permission is not permitted`)
    if (!['train','validation','test'].includes(row.splitStatus)) errors.push(`${row.sampleId}: trainingEligible but no model split assigned`)
  }
}

if (errors.length) {
  console.error(`DATA RELEASE VALIDATION FAILED (${errors.length})`)
  for (const error of errors) console.error(`- ${error}`)
  process.exit(1)
}

console.log(JSON.stringify({
  ok: true,
  diagnosticProfiles: index.records.length,
  referenceMedia: media.records.length,
  referenceAnnotations: annotations.length,
  transferDatasets: publicRegistry.datasets.length,
  trainingEligibleReferenceSamples: annotations.filter((r) => r.trainingEligible === true).length,
}, null, 2))
