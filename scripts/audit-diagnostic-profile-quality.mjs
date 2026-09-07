import fs from 'node:fs/promises'
import path from 'node:path'

const root = process.cwd()
const profilePath = path.join(root, 'data', 'diagnostic-profiles.json')
const profiles = JSON.parse(await fs.readFile(profilePath, 'utf8'))

const normalise = (value) => String(value ?? '').trim().toLowerCase().replace(/\s+/g, ' ')
const diagnosticExemptCategories = new Set(['Normal development', 'Insufficient evidence'])
const labBoundedCategories = new Set(['Bacterial pathogen', 'Viroid', 'Virus', 'Phytoplasma / Spiroplasma'])
const arthropodCategories = new Set(['Insect', 'Mite', 'Nematode'])
const rootCategories = new Set(['Root pathogen', 'Water / root-zone'])
const nutrientCategories = new Set(['Nutrient deficiency', 'Nutrient toxicity'])
const stopWords = new Set([
  'about','above','across','after','against','along','also','among','around','before','below','between','both','can','could','does','during','each','from','have','into','more','most','near','other','over','rather','remains','same','show','shows','than','that','their','then','there','these','this','through','toward','under','until','very','while','with','within','without','plant','plants','leaf','leaves','foliage','tissue','growth','symptom','symptoms','visible','visually','develop','develops','developed','progress','progresses','progressed',
])

const errors = []
const warnings = []

function uniqueNormalised(values = []) {
  return [...new Set(values.map(normalise).filter(Boolean))]
}

function hasAnyText(values = [], needles = []) {
  const text = values.map(normalise).join(' | ')
  return needles.some((needle) => text.includes(needle))
}

function stemToken(token) {
  if (token.length > 6 && token.endsWith('ies')) return `${token.slice(0, -3)}y`
  if (token.length > 6 && token.endsWith('ing')) return token.slice(0, -3)
  if (token.length > 5 && token.endsWith('ed')) return token.slice(0, -2)
  if (token.length > 5 && token.endsWith('es')) return token.slice(0, -2)
  if (token.length > 4 && token.endsWith('s')) return token.slice(0, -1)
  return token
}

function indicatorTokens(values = []) {
  const tokens = new Set()
  for (const value of values) {
    for (const raw of normalise(value).replace(/[^a-z0-9]+/g, ' ').split(' ')) {
      if (!raw || raw.length < 4 || stopWords.has(raw) || /^\d+$/.test(raw)) continue
      const token = stemToken(raw)
      if (token.length >= 4 && !stopWords.has(token)) tokens.add(token)
    }
  }
  return tokens
}

function jaccard(a, b) {
  if (!a.size || !b.size) return 0
  let shared = 0
  for (const item of a) if (b.has(item)) shared += 1
  const union = a.size + b.size - shared
  return union ? shared / union : 0
}

function qualityCheck(profile) {
  const prefix = `${profile.id ?? '<missing-id>'} (${profile.name ?? '<missing-name>'})`
  const indicators = uniqueNormalised(profile.indicators)
  const exclusions = uniqueNormalised(profile.exclusions)
  const confirmations = uniqueNormalised(profile.confirmation)
  const lookAlikes = uniqueNormalised(profile.lookAlikes)
  const sources = Array.isArray(profile.sources) ? profile.sources : []
  const exempt = diagnosticExemptCategories.has(profile.category)

  if (!profile.id || !profile.slug || !profile.name || !profile.category) errors.push(`${prefix}: missing core identity field`)
  if (!Array.isArray(profile.indicators) || !Array.isArray(profile.exclusions) || !Array.isArray(profile.confirmation) || !Array.isArray(profile.lookAlikes)) {
    errors.push(`${prefix}: diagnostic discriminator fields must be arrays`)
    return
  }

  if (profile.reviewStatus === 'reviewed' && !exempt) {
    if (indicators.length < 3) errors.push(`${prefix}: reviewed diagnostic profile needs at least 3 distinct indicators`)
    if (exclusions.length < 2) errors.push(`${prefix}: reviewed diagnostic profile needs at least 2 active exclusions`)
    if (confirmations.length < 2) errors.push(`${prefix}: reviewed diagnostic profile needs at least 2 confirmation steps`)
    if (lookAlikes.length < 2) errors.push(`${prefix}: reviewed diagnostic profile needs at least 2 realistic look-alikes`)
    if (sources.length < 1) errors.push(`${prefix}: reviewed diagnostic profile needs at least 1 source`)
  }

  if (!exempt && indicators.length && exclusions.length) {
    const exclusionSet = new Set(exclusions)
    const overlap = indicators.filter((item) => exclusionSet.has(item))
    if (overlap.length) errors.push(`${prefix}: ${overlap.length} item(s) appear as both indicator and exclusion: ${overlap.slice(0, 3).join('; ')}`)
  }

  if (labBoundedCategories.has(profile.category) && !hasAnyText(profile.confirmation, ['pcr', 'qpcr', 'laboratory', 'lab ', 'culture', 'sequenc', 'molecular'])) {
    errors.push(`${prefix}: lab-bounded category lacks an explicit laboratory/molecular confirmation requirement`)
  }

  if (arthropodCategories.has(profile.category) && !hasAnyText([...profile.confirmation, ...profile.indicators], ['underside', 'magnif', 'microscope', 'organism', 'egg', 'mite', 'insect', 'nematode'])) {
    warnings.push(`${prefix}: arthropod profile lacks an obvious direct-organism/underside/magnification discriminator`)
  }

  if (rootCategories.has(profile.category) && !hasAnyText([...profile.confirmation, ...profile.indicators], ['root', 'crown', 'rhiz', 'substrate'])) {
    warnings.push(`${prefix}: root-zone profile lacks an obvious root/crown/substrate discriminator`)
  }

  if (nutrientCategories.has(profile.category) && !hasAnyText(profile.confirmation, ['ph', 'ec', 'tissue', 'root-zone', 'root zone', 'solution', 'substrate', 'soil', 'water'])) {
    warnings.push(`${prefix}: nutrient profile lacks an obvious analytical/root-zone confirmation step`)
  }
}

for (const profile of profiles) qualityCheck(profile)

const confusionPairs = []
for (let i = 0; i < profiles.length; i += 1) {
  const a = profiles[i]
  if (diagnosticExemptCategories.has(a.category)) continue
  const ai = new Set(uniqueNormalised(a.indicators))
  const at = indicatorTokens(a.indicators)
  if (ai.size < 2) continue

  for (let j = i + 1; j < profiles.length; j += 1) {
    const b = profiles[j]
    if (diagnosticExemptCategories.has(b.category)) continue
    const bi = new Set(uniqueNormalised(b.indicators))
    const bt = indicatorTokens(b.indicators)
    if (bi.size < 2) continue

    const shared = [...ai].filter((item) => bi.has(item))
    const exactJaccard = jaccard(ai, bi)
    const sharedTokens = [...at].filter((item) => bt.has(item))
    const lexicalJaccard = jaccard(at, bt)

    if (shared.length >= 2 || exactJaccard >= 0.35 || lexicalJaccard >= 0.28) {
      confusionPairs.push({ a, b, shared, exactJaccard, sharedTokens, lexicalJaccard })
    }

    if (ai.size === bi.size && shared.length === ai.size && ai.size >= 2) {
      errors.push(`${a.id} and ${b.id}: exact duplicate normalized indicator sets (${ai.size} indicators)`)
    }
  }
}

confusionPairs.sort((x, y) => y.lexicalJaccard - x.lexicalJaccard || y.exactJaccard - x.exactJaccard || y.shared.length - x.shared.length)

const topPairs = confusionPairs.slice(0, 20).map((pair) => ({
  a: pair.a.slug,
  b: pair.b.slug,
  categories: [pair.a.category, pair.b.category],
  sharedIndicators: pair.shared.length,
  exactIndicatorOverlap: Number(pair.exactJaccard.toFixed(3)),
  lexicalIndicatorOverlap: Number(pair.lexicalJaccard.toFixed(3)),
  sharedTokens: pair.sharedTokens.slice(0, 10),
  exactExamples: pair.shared.slice(0, 3),
}))

if (warnings.length) {
  console.warn(`DIAGNOSTIC PROFILE QUALITY WARNINGS (${warnings.length})`)
  for (const warning of warnings) console.warn(`- ${warning}`)
}

console.log(JSON.stringify({
  ok: errors.length === 0,
  profileCount: profiles.length,
  reviewedProfiles: profiles.filter((profile) => profile.reviewStatus === 'reviewed').length,
  warnings: warnings.length,
  confusionPairsFound: confusionPairs.length,
  topConfusionPairs: topPairs,
}, null, 2))

if (errors.length) {
  console.error(`DIAGNOSTIC PROFILE QUALITY FAILED (${errors.length})`)
  for (const error of errors) console.error(`- ${error}`)
  process.exit(1)
}
