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

const errors = []
const warnings = []

function uniqueNormalised(values = []) {
  return [...new Set(values.map(normalise).filter(Boolean))]
}

function hasAnyText(values = [], needles = []) {
  const text = values.map(normalise).join(' | ')
  return needles.some((needle) => text.includes(needle))
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
  if (ai.size < 2) continue
  for (let j = i + 1; j < profiles.length; j += 1) {
    const b = profiles[j]
    if (diagnosticExemptCategories.has(b.category)) continue
    const bi = new Set(uniqueNormalised(b.indicators))
    if (bi.size < 2) continue
    const shared = [...ai].filter((item) => bi.has(item))
    const unionSize = new Set([...ai, ...bi]).size
    const jaccard = unionSize ? shared.length / unionSize : 0
    if (shared.length >= 2 || jaccard >= 0.35) {
      confusionPairs.push({ a, b, shared, jaccard })
    }
    if (ai.size === bi.size && shared.length === ai.size && ai.size >= 2) {
      errors.push(`${a.id} and ${b.id}: exact duplicate normalized indicator sets (${ai.size} indicators)`)
    }
  }
}

confusionPairs.sort((x, y) => y.jaccard - x.jaccard || y.shared.length - x.shared.length)

const topPairs = confusionPairs.slice(0, 15).map((pair) => ({
  a: pair.a.slug,
  b: pair.b.slug,
  categories: [pair.a.category, pair.b.category],
  sharedIndicators: pair.shared.length,
  indicatorOverlap: Number(pair.jaccard.toFixed(3)),
  examples: pair.shared.slice(0, 3),
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
