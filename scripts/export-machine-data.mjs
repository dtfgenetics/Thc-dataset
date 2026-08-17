import fs from 'node:fs/promises'
import path from 'node:path'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { pathToFileURL } from 'node:url'

const execFileAsync = promisify(execFile)

// Canonical deterministic exporter for machine-readable diagnostic release files.
// The project TypeScript CLI performs source compilation. This avoids relying on
// unstable runtime exports from the TypeScript package itself.
// Generated files never overwrite manually reviewed reference-media.json or manifest.json.

const root = process.cwd()
const outDir = path.join(root, 'data')
const profilesDir = path.join(outDir, 'profiles')
const tempDir = path.join(root, '.dataset-export-tmp')
const minimumExpectedProfiles = 35
const requiredProfileFields = [
  'id', 'slug', 'name', 'category', 'severity', 'reviewStatus', 'summary',
  'affectedParts', 'stages', 'indicators', 'exclusions', 'progression',
  'lookAlikes', 'confirmation', 'immediateActions', 'correctivePlan',
  'prevention', 'warnings', 'sources', 'media',
]

await fs.mkdir(outDir, { recursive: true })
await fs.rm(tempDir, { recursive: true, force: true })
await fs.mkdir(tempDir, { recursive: true })

async function compileCanonicalSources() {
  const args = [
    '--no-install', 'tsc',
    '--ignoreConfig',
    'src/data/issues.ts',
    'src/data/supplemental-issues.ts',
    '--target', 'ES2022',
    '--module', 'ES2022',
    '--moduleResolution', 'Bundler',
    '--rootDir', 'src',
    '--outDir', tempDir,
    '--skipLibCheck',
    '--declaration', 'false',
    '--sourceMap', 'false',
    '--noEmitOnError', 'true',
  ]
  await execFileAsync('npx', args, { cwd: root, maxBuffer: 16 * 1024 * 1024 })
}

async function loadCompiledModule(relativePath) {
  const compiledPath = path.join(tempDir, relativePath)
  return import(`${pathToFileURL(compiledPath).href}?v=${Date.now()}`)
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

try {
  await compileCanonicalSources()
  const mainModule = await loadCompiledModule('data/issues.js')
  const supplementalModule = await loadCompiledModule('data/supplemental-issues.js')

  const primaryIssues = Array.isArray(mainModule.issues) ? mainModule.issues : []
  const supplementalIssues = Array.isArray(supplementalModule.supplementalIssues) ? supplementalModule.supplementalIssues : []
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
  }

  const sourceMap = new Map()
  const mediaMap = new Map()
  for (const issue of diagnosticProfiles) {
    for (const source of issue.sources ?? []) {
      const key = source.doi || source.url || `${source.title}|${source.organization || ''}`
      const previous = sourceMap.get(key)
      if (previous && canonicalKey(previous) !== canonicalKey(source)) throw new Error(`Conflicting source metadata for ${key}`)
      if (!previous) sourceMap.set(key, source)
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

  await fs.rm(profilesDir, { recursive: true, force: true })
  await fs.mkdir(profilesDir, { recursive: true })
  for (const profile of diagnosticProfiles) await fs.writeFile(path.join(profilesDir, `${profile.id}.json`), stableJson(profile), 'utf8')
  await fs.writeFile(path.join(profilesDir, 'index.json'), stableJson({ schemaVersion: '1.0.0', recordCount: profileIndex.length, records: profileIndex }), 'utf8')

  const exportManifest = {
    schemaVersion: '2.1.0',
    deterministic: true,
    compiler: 'project tsc CLI',
    sourceFiles: ['src/data/issues.ts', 'src/data/supplemental-issues.ts'],
    counts: {
      primaryDiagnosticProfiles: primaryIssues.length,
      supplementalDiagnosticProfiles: supplementalIssues.length,
      diagnosticProfiles: diagnosticProfiles.length,
      sources: sources.length,
      profileReferenceMedia: profileReferenceMedia.length,
      trainingEligibleMedia: trainingEligibleMedia.length,
    },
    files: {
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
      'Generated output does not overwrite curated data/reference-media.json.',
      'Generated output does not overwrite curated data/manifest.json.',
      'Duplicate profile ids and slugs fail closed.',
      'Conflicting duplicate source or media metadata fails closed.',
      'A partial export below the established 35-profile baseline fails closed.',
    ],
  }

  await Promise.all([
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
