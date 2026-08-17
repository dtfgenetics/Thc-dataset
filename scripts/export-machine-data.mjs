import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import ts from 'typescript'

const root = process.cwd()
const outDir = path.join(root, 'data')
const tempDir = path.join(root, '.dataset-export-tmp')

await fs.mkdir(outDir, { recursive: true })
await fs.mkdir(tempDir, { recursive: true })

async function loadTsModule(sourcePath, tempName) {
  const source = await fs.readFile(path.join(root, sourcePath), 'utf8')
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ES2022,
      importsNotUsedAsValues: ts.ImportsNotUsedAsValues.Remove,
    },
    fileName: sourcePath,
  }).outputText

  const tempPath = path.join(tempDir, tempName)
  await fs.writeFile(tempPath, compiled, 'utf8')
  return import(`${pathToFileURL(tempPath).href}?v=${Date.now()}`)
}

const mainModule = await loadTsModule('src/data/issues.ts', 'issues.mjs')
const supplementalModule = await loadTsModule('src/data/supplemental-issues.ts', 'supplemental-issues.mjs')

const primaryIssues = Array.isArray(mainModule.issues) ? mainModule.issues : []
const supplementalIssues = Array.isArray(supplementalModule.supplementalIssues) ? supplementalModule.supplementalIssues : []
const diagnosticProfiles = [...primaryIssues, ...supplementalIssues]

if (diagnosticProfiles.length === 0) {
  throw new Error('No diagnostic profiles were exported. Refusing to write an empty dataset.')
}

const duplicates = diagnosticProfiles
  .map((item) => item.id)
  .filter((id, index, all) => all.indexOf(id) !== index)
if (duplicates.length) {
  throw new Error(`Duplicate diagnostic profile ids: ${[...new Set(duplicates)].join(', ')}`)
}

const sourceMap = new Map()
const mediaMap = new Map()
for (const issue of diagnosticProfiles) {
  for (const source of issue.sources ?? []) {
    const key = source.doi || source.url || `${source.title}|${source.organization || ''}`
    if (!sourceMap.has(key)) sourceMap.set(key, source)
  }
  for (const media of issue.media ?? []) {
    const enriched = {
      ...media,
      issueId: issue.id,
      issueSlug: issue.slug,
      issueName: issue.name,
      issueCategory: issue.category,
    }
    if (!mediaMap.has(media.id)) mediaMap.set(media.id, enriched)
  }
}

const sources = [...sourceMap.values()]
const referenceMedia = [...mediaMap.values()]
const trainingEligibleMedia = referenceMedia.filter((item) => item.trainingEligible === true && item.trainingPermission === 'permitted')

const generatedAt = new Date().toISOString()
const manifest = {
  schemaVersion: '1.0.0',
  generatedAt,
  sourceFiles: ['src/data/issues.ts', 'src/data/supplemental-issues.ts'],
  counts: {
    primaryDiagnosticProfiles: primaryIssues.length,
    supplementalDiagnosticProfiles: supplementalIssues.length,
    diagnosticProfiles: diagnosticProfiles.length,
    sources: sources.length,
    referenceMedia: referenceMedia.length,
    trainingEligibleMedia: trainingEligibleMedia.length,
  },
  files: {
    diagnosticProfiles: 'data/diagnostic-profiles.json',
    diagnosticProfilesCsv: 'data/diagnostic-profiles.csv',
    sources: 'data/sources.json',
    referenceMedia: 'data/reference-media.json',
    trainingEligibleMedia: 'data/training-eligible-media.json',
  },
  note: 'Reference media metadata is not equivalent to an image-training corpus. Only assets explicitly marked trainingEligible=true and trainingPermission=permitted are included in the training-eligible manifest.',
}

function stableJson(value) {
  return `${JSON.stringify(value, null, 2)}\n`
}

function csvCell(value) {
  const text = value == null ? '' : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

const csvHeaders = [
  'id','slug','name','scientificName','category','severity','reviewStatus','summary',
  'affectedParts','stages','indicators','exclusions','lookAlikes','confirmation',
  'immediateActions','correctivePlan','prevention','warnings','sourceCount','mediaCount'
]

const csvRows = diagnosticProfiles.map((issue) => {
  const row = {
    id: issue.id,
    slug: issue.slug,
    name: issue.name,
    scientificName: issue.scientificName ?? '',
    category: issue.category,
    severity: issue.severity,
    reviewStatus: issue.reviewStatus,
    summary: issue.summary,
    affectedParts: (issue.affectedParts ?? []).join(' | '),
    stages: (issue.stages ?? []).join(' | '),
    indicators: (issue.indicators ?? []).join(' | '),
    exclusions: (issue.exclusions ?? []).join(' | '),
    lookAlikes: (issue.lookAlikes ?? []).join(' | '),
    confirmation: (issue.confirmation ?? []).join(' | '),
    immediateActions: (issue.immediateActions ?? []).join(' | '),
    correctivePlan: (issue.correctivePlan ?? []).join(' | '),
    prevention: (issue.prevention ?? []).join(' | '),
    warnings: (issue.warnings ?? []).join(' | '),
    sourceCount: (issue.sources ?? []).length,
    mediaCount: (issue.media ?? []).length,
  }
  return csvHeaders.map((key) => csvCell(row[key])).join(',')
})

await Promise.all([
  fs.writeFile(path.join(outDir, 'diagnostic-profiles.json'), stableJson(diagnosticProfiles)),
  fs.writeFile(path.join(outDir, 'diagnostic-profiles.csv'), `${csvHeaders.map(csvCell).join(',')}\n${csvRows.join('\n')}\n`),
  fs.writeFile(path.join(outDir, 'sources.json'), stableJson(sources)),
  fs.writeFile(path.join(outDir, 'reference-media.json'), stableJson(referenceMedia)),
  fs.writeFile(path.join(outDir, 'training-eligible-media.json'), stableJson(trainingEligibleMedia)),
  fs.writeFile(path.join(outDir, 'manifest.json'), stableJson(manifest)),
])

await fs.rm(tempDir, { recursive: true, force: true })

console.log(JSON.stringify(manifest, null, 2))
