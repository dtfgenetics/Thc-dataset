import responsePolicies from '../../backend/config/diagnostic-response-policy.json'
import type { Differential, EvidenceFile, GrowContext, IssueRecord } from '../types'

const normalise = (value: string) => value.trim().toLowerCase()

interface DiagnosticResponsePolicy {
  policy_id: string
  canonical_ids: string[]
  photo_only_max_confidence: number
  photo_can_confirm: boolean | string
  required_confirmation?: string[]
}

const policies = responsePolicies as DiagnosticResponsePolicy[]
const defaultPolicy = policies.find((policy) => policy.policy_id === 'POL-DEFAULT')

const laboratoryBoundedCategories = new Set([
  'Bacterial pathogen',
  'Viroid',
  'Virus',
  'Phytoplasma / Spiroplasma',
])

const microscopicMiteSlugs = new Set(['hemp-russet-mite', 'broad-mite'])

const needsRootZoneChemistry = (issue: IssueRecord) =>
  issue.category === 'Nutrient deficiency'
  || issue.category === 'Nutrient toxicity'
  || issue.category === 'Water / root-zone'
  || issue.category === 'Root pathogen'

const needsWateringContext = (issue: IssueRecord) =>
  issue.category === 'Water / root-zone'
  || issue.category === 'Root pathogen'
  || issue.category === 'Environmental stress'

const buildIndicatorFrequency = (records: IssueRecord[]) => {
  const frequency = new Map<string, number>()
  for (const issue of records) {
    // Count an indicator once per diagnosis. Repeated wording inside one record
    // must not make a symptom look more generic than it is across the catalog.
    const uniqueIndicators = new Set(issue.indicators.map(normalise))
    for (const indicator of uniqueIndicators) {
      frequency.set(indicator, (frequency.get(indicator) ?? 0) + 1)
    }
  }
  return frequency
}

const indicatorSignalWeight = (frequency: number) => {
  if (frequency <= 1) return 4
  if (frequency === 2) return 3.5
  if (frequency <= 4) return 3
  if (frequency <= 8) return 2.5
  return 2
}

const responsePolicyFor = (issue: IssueRecord) => {
  if (issue.responsePolicyId) {
    const explicit = policies.find((policy) => policy.policy_id === issue.responsePolicyId)
    if (explicit) return explicit
  }
  if (issue.canonicalId) {
    const canonical = policies.find((policy) => policy.canonical_ids.includes(issue.canonicalId as string))
    if (canonical) return canonical
  }
  return defaultPolicy
}

const confidenceAtCeiling = (ceiling: number): Differential['confidence'] => {
  if (ceiling >= 0.85) return 'High'
  if (ceiling >= 0.6) return 'Moderate'
  return 'Low'
}

const lowerConfidenceTo = (
  confidence: Differential['confidence'],
  ceiling: Differential['confidence'],
): Differential['confidence'] => {
  const order: Record<Differential['confidence'], number> = { Low: 0, Moderate: 1, High: 2 }
  return order[confidence] <= order[ceiling] ? confidence : ceiling
}

const applyResponsePolicy = (
  issue: IssueRecord,
  confidence: Differential['confidence'],
  missing: string[],
): Differential['confidence'] => {
  const policy = responsePolicyFor(issue)
  const rawCap = issue.photoOnlyMaxConfidence ?? policy?.photo_only_max_confidence
  if (typeof rawCap !== 'number' || !Number.isFinite(rawCap)) return confidence

  // The controlled backend stores normalized 0–1 ceilings. Percentage-style
  // values are tolerated for future imported records without changing meaning.
  const cap = Math.max(0, Math.min(1, rawCap > 1 ? rawCap / 100 : rawCap))
  const capped = lowerConfidenceTo(confidence, confidenceAtCeiling(cap))

  if (capped !== confidence && !missing.includes('response policy limits photo-only confidence')) {
    missing.push('response policy limits photo-only confidence')
  }

  if (policy?.photo_can_confirm === false) {
    const required = policy.required_confirmation ?? []
    if (!required.length) {
      if (!missing.includes('non-visual confirmation required by issue confidence policy')) {
        missing.push('non-visual confirmation required by issue confidence policy')
      }
    } else {
      for (const item of required) {
        const label = `confirmation: ${item}`
        if (!missing.includes(label)) missing.push(label)
      }
    }
  }

  return capped
}

export function rankDifferentials(
  records: IssueRecord[],
  context: GrowContext,
  evidence: EvidenceFile[],
): Differential[] {
  const selected = new Set(context.symptoms.map(normalise))
  const indicatorFrequency = buildIndicatorFrequency(records)
  const hasRootView = evidence.some((item) => item.slot === 'root-crown')
  const hasUnderside = evidence.some((item) => item.slot === 'underside')
  const hasWholePlant = evidence.some((item) => item.slot === 'whole-plant')
  const hasCloseUp = evidence.some((item) => item.slot === 'close-up')

  const ranked = records
    .map((issue) => {
      const matched = issue.indicators.filter((indicator) => selected.has(normalise(indicator)))
      const contradictory = issue.exclusions.filter((indicator) => selected.has(normalise(indicator)))

      // Not every symptom carries the same information. A sign shared by many
      // diagnoses (for example generic yellowing or stunting) is useful, but it
      // should not outweigh a rarer, more discriminating pattern simply because
      // several common symptoms were selected.
      const supportingScore = matched.reduce((total, indicator) => {
        const frequency = indicatorFrequency.get(normalise(indicator)) ?? 1
        return total + indicatorSignalWeight(frequency)
      }, 0)
      const contradictionScore = contradictory.reduce((total, indicator) => {
        const frequency = indicatorFrequency.get(normalise(indicator)) ?? 1
        return total + Math.max(4, indicatorSignalWeight(frequency) + 1)
      }, 0)
      let score = supportingScore - contradictionScore

      if (context.stage && issue.stages.includes(context.stage)) score += 1
      if (hasRootView && (issue.category === 'Root pathogen' || issue.category === 'Water / root-zone')) score += 1
      if (hasUnderside && (issue.category === 'Mite' || issue.category === 'Insect')) score += 1

      const missing: string[] = []
      if (!hasWholePlant) missing.push('whole-plant view')
      if (!hasCloseUp) missing.push('affected-tissue close-up')
      if ((issue.category === 'Mite' || issue.category === 'Insect') && !hasUnderside) missing.push('leaf-underside image')
      if ((issue.category === 'Root pathogen' || issue.category === 'Water / root-zone') && !hasRootView) missing.push('root or crown view')
      if (laboratoryBoundedCategories.has(issue.category)) missing.push('validated laboratory test')
      if (microscopicMiteSlugs.has(issue.slug)) missing.push('microscope-confirmed mite identification')

      // Optional grow context is requested only when it can separate plausible causes.
      // It must never block the first image/video analysis.
      if (needsRootZoneChemistry(issue) && !context.ph) missing.push('measured pH')
      if (needsRootZoneChemistry(issue) && !context.ec) missing.push('measured EC/PPM')
      if (needsWateringContext(issue) && !context.watering) missing.push('recent irrigation / substrate-moisture context')

      // Require multiple independent symptom signals before confidence can rise.
      // A single visually compatible symptom is a lead, not a diagnosis.
      let confidence: Differential['confidence'] =
        score >= 10 && matched.length >= 3 && contradictory.length === 0
          ? 'High'
          : score >= 5 && matched.length >= 2
            ? 'Moderate'
            : 'Low'

      // Evidence gates prevent symptom overlap from being mistaken for confirmation.
      if (laboratoryBoundedCategories.has(issue.category)) confidence = 'Low'

      if (issue.category === 'Root pathogen' && !hasRootView) confidence = 'Low'

      if (issue.category === 'Mite') {
        if (!hasUnderside) confidence = 'Low'
        else if (microscopicMiteSlugs.has(issue.slug) && confidence === 'High') confidence = 'Moderate'
      }

      if (issue.category === 'Insect' && !hasUnderside && confidence === 'High') confidence = 'Moderate'

      if (
        (issue.category === 'Nutrient deficiency' || issue.category === 'Nutrient toxicity')
        && (!context.ph || !context.ec)
        && confidence === 'High'
      ) {
        confidence = 'Moderate'
      }

      if ((!hasWholePlant || !hasCloseUp) && confidence === 'High') confidence = 'Moderate'

      // Use the same controlled response policy as the backend adjudicator so
      // visual-only confidence cannot silently exceed the condition-specific ceiling.
      confidence = applyResponsePolicy(issue, confidence, missing)

      return {
        issue,
        confidence,
        score,
        supporting: matched,
        contradicting: contradictory,
        missing,
      } satisfies Differential
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)

  // A high absolute score is not enough when another diagnosis explains the
  // same evidence nearly as well. Preserve the differential and ask for the
  // observation/test that separates the leading look-alikes.
  return ranked.map((item, index) => {
    let confidence = item.confidence
    const missing = [...item.missing]

    if (index > 0 && confidence === 'High') confidence = 'Moderate'

    if (index === 0 && ranked.length > 1) {
      const margin = item.score - ranked[1].score
      if (margin < 2) {
        if (confidence === 'High') confidence = 'Moderate'
        if (!missing.includes('additional discriminating evidence between the leading look-alikes')) {
          missing.push('additional discriminating evidence between the leading look-alikes')
        }
      }
    }

    return { ...item, confidence, missing }
  })
}

export async function inspectEvidenceFile(file: File) {
  const notes: string[] = []
  if (file.size < 90_000) notes.push('File is small; fine symptom detail may be missing.')
  if (file.size > 18_000_000) notes.push('Large file; upload may be slow on mobile data.')

  const url = URL.createObjectURL(file)
  try {
    if (file.type.startsWith('video/')) {
      const metadata = await new Promise<{ width: number; height: number; duration: number }>((resolve, reject) => {
        const video = document.createElement('video')
        video.onloadedmetadata = () => resolve({ width: video.videoWidth, height: video.videoHeight, duration: video.duration })
        video.onerror = reject
        video.src = url
      })
      if (metadata.duration > 30.5) notes.push('Video is longer than 30 seconds; trim it before analysis.')
      if (metadata.width < 720 || metadata.height < 480) notes.push('Low video resolution; fine symptom detail may be missing.')
      return { ...metadata, quality: notes.length ? 'review' as const : 'good' as const, notes }
    }
    const dimensions = await new Promise<{ width: number; height: number }>((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight })
      image.onerror = reject
      image.src = url
    })
    if (dimensions.width < 900 || dimensions.height < 700) notes.push('Low resolution; retake closer or at a higher setting.')
    if (Math.max(dimensions.width, dimensions.height) / Math.min(dimensions.width, dimensions.height) > 3) notes.push('Very narrow crop; include more surrounding tissue.')
    return { ...dimensions, quality: notes.length ? 'review' as const : 'good' as const, notes }
  } finally {
    URL.revokeObjectURL(url)
  }
}

export function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}
