import fs from 'node:fs/promises'
import path from 'node:path'
import { createRequire } from 'node:module'

// Canonical deterministic exporter for machine-readable diagnostic release files.
// The application catalog is the single reviewed source boundary. This keeps
// source errata, controlled IDs, category normalization and verified-media
// enrichment identical between the UI and machine-readable release.
//
// Materialization uses the already-installed TypeScript compiler API only to
// transpile the src/data modules to temporary CommonJS. The repository's normal
// `npm run check` remains the independent full TypeScript type-safety gate.

const root = process.cwd()
const outDir = path.join(root, 'data')
const profilesDir = path.join(outDir, 'profiles')
const tempDir = path.join(root, '.dataset-export-tmp')
const minimumExpectedProfiles = 54
const requiredProfileFields = [
  'id', 'slug', 'name', 'category', 'severity', 'reviewStatus', 'summary',
  'affectedParts', 'stages', 'indicators', 'exclusions', 'progression',
  'lookAlikes', 'confirmation', 'immediateActions', 'correctivePlan',
  'prevention', 'warnings', 'sources', 'media',
]

await fs.mkdir(outDir, { recursive: true })
await fs.rm(tempDir, { recursive: true, force: true })
await fs.mkdir(tempDir, { recursive: true })

async function loadTypeScriptApi() {
  const namespace = await import('typescript')
  const candidates = [
    namespace,
    namespace.default,
    namespace.default?.default,
    namespace['module.exports'],
    namespace.default?.['module.exports'],
  ]
  const ts = candidates.find((candidate) =>
    candidate &&
    typeof candidate.transpileModule === 'function' &&
    candidate.ScriptTarget &&
    candidate.ModuleKind,
  )
  if (!ts) {
    const shapes = candidates.filter(Boolean).map((candidate) => Object.keys(candidate).slice(0, 12))
    throw new Error(`Unable to resolve TypeScript compiler API. Module shapes: ${JSON.stringify(shapes)}`)
  }
  return ts
}

async function compileCanonicalCatalog() {
  const ts = await loadTypeScriptApi()
  const sourceDir = path.join(root, 'src', 'data')
  const outputDir = path.join(tempDir, 'data')
  await fs.mkdir(outputDir, { recursive: true })

  const entries = (await fs.readdir(sourceDir, { withFileTypes: true }))
    .filter((entry) => entry.isFile() && entry.name.endsWith('.ts'))
    .map((entry) => entry.name)
    .sort()

  if (!entries.includes('catalog.ts')) throw new Error('Canonical src/data/catalog.ts was not found')

  for (const name of entries) {
    const inputPath = path.join(sourceDir, name)
    const source = await fs.readFile(inputPath, 'utf8')
    const result = ts.transpileModule(source, {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        esModuleInterop: true,
        sourceMap: false,
        declaration: false,
      },
      fileName: inputPath,
      reportDiagnostics: true,
    })

    const hardDiagnostics = (result.diagnostics ?? []).filter((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error)
    if (hardDiagnostics.length) {
      const text = hardDiagnostics.map((diagnostic) => ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n')).join(' | ')
      throw new Error(`${name}: TypeScript transpile diagnostics: ${text}`)
    }

    await fs.writeFile(path.join(outputDir, name.replace(/\.ts$/, '.js')), result.outputText, 'utf8')
  }

  await fs.writeFile(path.join(tempDir, 'package.json'), '{"type":"commonjs"}\n', 'utf8')
  return path.join(outputDir, 'catalog.js')
}

function stableJson(value) {
  return `${JSON.stringify(value, null, 2)}\n`
}

function csvCell(value) {
  const text = value == null ? '' : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

function canonicalKey(value) {
  return JSON.stringify(value)
}

function uniqueStrings(values = []) {
  return [...new Set(values.filter(Boolean))]
}

function mergeSourceRecords(previous, incoming, key) {
  if (!previous) return incoming

  for (const field of ['title', 'url', 'doi', 'organization', 'publisher', 'publicationDate', 'year']) {
    const a = previous[field]
    const b = incoming[field]
    if (a != null && b != null && a !== b) {
      throw new Error(`Conflicting source metadata for ${key}: ${field} differs (${a} vs ${b})`)
    }
  }

  return {
    ...previous,
    ...Object.fromEntries(Object.entries(incoming).filter(([, value]) => value != null)),
    accessedDate: [previous.accessedDate, incoming.accessedDate].filter(Boolean).sort().at(-1),
    authors: uniqueStrings([...(previous.authors ?? []), ...(incoming.authors ?? [])]),
    supportedClaims: uniqueStrings([...(previous.supportedClaims ?? []), ...(incoming.supportedClaims ?? [])]),
  }
}

try {
  const compiledCatalog = await compileCanonicalCatalog()
  const requireFromTemp = createRequire(path.join(tempDir, 'package.json'))
  const catalog = requireFromTemp(compiledCatalog)

  const primaryIssues = Array.isArray(catalog.coreIssues) ? catalog.coreIssues : []
  const supplementalIssues = Array.isArray(catalog.supplementalIssues) ? catalog.supplementalIssues : []
  const diagnosticProfiles = [...primaryIssues, ...supplementalIssues]
    .sort((a, b) => String(a.id).localeCompare(String(b.id)))

  if (diagnosticProfiles.length < minimumExpectedProfiles) {
    throw new Error(`Expected at least ${minimumExpectedProfiles} diagnostic profiles, found ${diagnosticProfiles.length}. Refusing partial export.`)
  }

  const duplicateIds = diagnosticProfiles.map((item) => item.id).filter((id, index, all) => all.indexOf(id) !== index)
  if (duplicateIds.length) throw new Error(`Duplicate diagnostic profile ids: ${[...new Set(duplicateIds)].join(', ')}`)

  const duplicateSlugs = diagnosticProfiles.map((item) => item.slug).filter((slug, index, all) => all.indexOf(slug) !== index)
  if (duplicateSlugs.length) throw new Error(`Duplicate diagnostic profile slugs: ${[...new Set(duplicateSlugs)].join(', ')}`)

  for (const profile of diagnosticProfiles) {
    const missing = requiredProfileFields.filter((field) => profile[field] == null)
    if (missing.length) throw new Error(`${profile.id || '<missing-id>'}: missing required fields ${missing.join(', ')}`)
    for (const field of ['affectedParts','stages','indicators','exclusions','progression','lookAlikes','confirmation','immediateActions','correctivePlan','prevention','warnings','sources','media']) {
      if (!Array.isArray(profile[field])) throw new Error(`${profile.id}: ${field} must be an array`)
    }
    if (!profile.sources.length) throw new Error(`${profile.id}: reviewed profile has no evidence source`)
  }

  const sourceMap = new Map()
  const mediaMap = new Map()
  for (const issue of diagnosticProfiles) {
    for (const source of issue.sources ?? []) {
      const key = source.doi || source.url || `${source.title}|${source.organization || ''}`
      sourceMap.set(key, mergeSourceRecords(sourceMap.get(key), source, key))
    }

    for (const media of issue.media ?? []) {
      if (!media.id) throw new Error(`${issue.id}: media record is missing id`)
      const enriched = { ...media, issueId: issue.id, issueSlug: issue.slug, issueName: issue.name, issueCategory: issue.category }
      const previous = mediaMap.get(media.id)
      if (previous && canonicalKey(previous) !== canonicalKey(enriched)) throw new Error(`Conflicting media metadata for ${media.id}`)
      if (!previous) mediaMap.set(media.id, enriched)
    }
  }

  const sources = [...sourceMap.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([sourceKey, source]) => ({ sourceKey, ...source }))
  const profileReferenceMedia = [...mediaMap.values()].sort((a, b) => String(a.id).localeCompare(String(b.id)))
  const trainingEligibleMedia = profileReferenceMedia.filter((item) => item.trainingEligible === true && item.trainingPermission === 'permitted')

  const coreIds = new Set(primaryIssues.map((item) => item.id))
  const profileIndex = diagnosticProfiles.map((profile) => ({
    id: profile.id,
    slug: profile.slug,
    name: profile.name,
    category: profile.category,
    severity: profile.severity,
    reviewStatus: profile.reviewStatus,
    sourceCount: profile.sources.length,
    mediaCount: profile.media.length,
    path: `data/profiles/${profile.id}.json`,
  }))

  const diagnosticIndexRecords = diagnosticProfiles.map((profile) => ({
    id: profile.id,
    slug: profile.slug,
    name: profile.name,
    category: profile.category,
    severity: profile.severity,
    reviewStatus: profile.reviewStatus,
    recordType: 'diagnostic-profile',
    sourceLayer: coreIds.has(profile.id) ? 'core' : 'supplemental',
    sourceFile: 'src/data/catalog.ts',
    path: `data/profiles/${profile.id}.json`,
  }))

  const csvHeaders = ['id','slug','name','scientificName','category','severity','reviewStatus','summary','affectedParts','stages','indicators','exclusions','lookAlikes','confirmation','immediateActions','correctivePlan','prevention','warnings','sourceCount','mediaCount']
  const csvRows = diagnosticProfiles.map((issue) => {
    const row = {
      id: issue.id, slug: issue.slug, name: issue.name, scientificName: issue.scientificName ?? '', category: issue.category,
      severity: issue.severity, reviewStatus: issue.reviewStatus, summary: issue.summary,
      affectedParts: issue.affectedParts.join(' | '), stages: issue.stages.join(' | '), indicators: issue.indicators.join(' | '),
      exclusions: issue.exclusions.join(' | '), lookAlikes: issue.lookAlikes.join(' | '), confirmation: issue.confirmation.join(' | '),
      immediateActions: issue.immediateActions.join(' | '), correctivePlan: issue.correctivePlan.join(' | '), prevention: issue.prevention.join(' | '),
      warnings: issue.warnings.join(' | '), sourceCount: issue.sources.length, mediaCount: issue.media.length,
    }
    return csvHeaders.map((key) => csvCell(row[key])).join(',')
  })

  const indexCsvHeaders = ['id','slug','name','category','severity','reviewStatus','sourceLayer','recordType','path']
  const indexCsvRows = diagnosticIndexRecords.map((record) => indexCsvHeaders.map((key) => csvCell(record[key])).join(','))

  await fs.rm(profilesDir, { recursive: true, force: true })
  await fs.mkdir(profilesDir, { recursive: true })
  for (const profile of diagnosticProfiles) await fs.writeFile(path.join(profilesDir, `${profile.id}.json`), stableJson(profile), 'utf8')
  await fs.writeFile(path.join(profilesDir, 'index.json'), stableJson({ schemaVersion: '1.1.0', recordCount: profileIndex.length, records: profileIndex }), 'utf8')

  const diagnosticIndex = {
    schemaVersion: '2.0.0',
    status: 'generated-from-reviewed-catalog',
    recordCount: diagnosticIndexRecords.length,
    description: 'Deterministic machine-readable index generated from the same reviewed catalog used by the application. Source errata and category normalization are applied before export.',
    records: diagnosticIndexRecords,
  }

  const exportManifest = {
    schemaVersion: '2.0.0',
    deterministic: true,
    compiler: 'installed TypeScript compiler API transpile-only; repository TypeScript validation runs independently',
    sourceFiles: ['src/data/catalog.ts', 'src/data/issues.ts', 'src/data/supplemental-issues.ts', 'src/data/expanded-issues.ts', 'src/data/expanded-issues-batch2.ts'],
    counts: {
      primaryDiagnosticProfiles: primaryIssues.length,
      supplementalDiagnosticProfiles: supplementalIssues.length,
      diagnosticProfiles: diagnosticProfiles.length,
      sources: sources.length,
      profileReferenceMedia: profileReferenceMedia.length,
      trainingEligibleMedia: trainingEligibleMedia.length,
    },
    files: {
      diagnosticIndex: 'data/diagnostic-index.json',
      diagnosticIndexCsv: 'data/diagnostic-index.csv',
      diagnosticProfiles: 'data/diagnostic-profiles.json',
      diagnosticProfilesJsonl: 'data/diagnostic-profiles.jsonl',
      diagnosticProfilesCsv: 'data/diagnostic-profiles.csv',
      profileDirectory: 'data/profiles',
      profileIndex: 'data/profiles/index.json',
      sources: 'data/sources.json',
      profileReferenceMedia: 'data/profile-reference-media.json',
      trainingEligibleMedia: 'data/training-eligible-media.json',
    },
    safeguards: [
      'The application catalog is the only export boundary; raw source modules cannot bypass catalog-level errata normalization.',
      'Generated output does not overwrite curated data/reference-media.json.',
      'Generated output does not overwrite curated data/manifest.json.',
      'Diagnostic index JSON and CSV are generated from the same profile set rather than maintained manually.',
      'Duplicate profile ids and slugs fail closed.',
      'Duplicate evidence sources are merged only when identity metadata agrees; claim and author lists are unioned deterministically.',
      'Conflicting duplicate media metadata fails closed.',
      `A partial export below the established ${minimumExpectedProfiles}-profile baseline fails closed.`,
      'The full repository TypeScript check remains a separate required CI gate from dataset materialization.',
    ],
  }

  await Promise.all([
    fs.writeFile(path.join(outDir, 'diagnostic-index.json'), stableJson(diagnosticIndex)),
    fs.writeFile(path.join(outDir, 'diagnostic-index.csv'), `${indexCsvHeaders.map(csvCell).join(',')}\n${indexCsvRows.join('\n')}\n`),
    fs.writeFile(path.join(outDir, 'diagnostic-profiles.json'), stableJson(diagnosticProfiles)),
    fs.writeFile(path.join(outDir, 'diagnostic-profiles.jsonl'), `${diagnosticProfiles.map((item) => JSON.stringify(item)).join('\n')}\n`),
    fs.writeFile(path.join(outDir, 'diagnostic-profiles.csv'), `${csvHeaders.map(csvCell).join(',')}\n${csvRows.join('\n')}\n`),
    fs.writeFile(path.join(outDir, 'sources.json'), stableJson(sources)),
    fs.writeFile(path.join(outDir, 'profile-reference-media.json'), stableJson(profileReferenceMedia)),
    fs.writeFile(path.join(outDir, 'training-eligible-media.json'), stableJson(trainingEligibleMedia)),
    fs.writeFile(path.join(outDir, 'export-manifest.json'), stableJson(exportManifest)),
  ])

  console.log(JSON.stringify(exportManifest, null, 2))
} finally {
  await fs.rm(tempDir, { recursive: true, force: true })
}
