import responsePolicies from '../../backend/config/diagnostic-response-policy.json'
import type { Differential, EvidenceFile, GrowContext, GrowLogEntry, IssueRecord } from '../types'

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

const responsePolicyBySlug: Record<string, string> = {
  'hop-latent-viroid': 'POL-HLVD',
  'pythium-root-rot': 'POL-PYTHIUM',
  'powdery-mildew': 'POL-PM',
  'botrytis-gray-mold-bud-rot': 'POL-BOTRYTIS',
  'two-spotted-spider-mites': 'POL-SPIDER-MITE',
  'hemp-russet-mite': 'POL-BROAD-RUSSET',
  'broad-mite': 'POL-BROAD-RUSSET',
  'acidic-extreme-substrate-ph-stress': 'POL-PH-LOCKOUT',
}

const laboratoryBoundedCategories = new Set(['Bacterial pathogen', 'Viroid', 'Virus', 'Phytoplasma / Spiroplasma'])
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
    const uniqueIndicators = new Set(issue.indicators.map(normalise))
    for (const indicator of uniqueIndicators) frequency.set(indicator, (frequency.get(indicator) ?? 0) + 1)
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
  const slugPolicyId = responsePolicyBySlug[issue.slug]
  if (slugPolicyId) {
    const slugPolicy = policies.find((policy) => policy.policy_id === slugPolicyId)
    if (slugPolicy) return slugPolicy
  }
  return defaultPolicy
}

const confidenceAtCeiling = (ceiling: number): Differential['confidence'] => {
  if (ceiling >= 0.85) return 'High'
  if (ceiling >= 0.6) return 'Moderate'
  return 'Low'
}

const lowerConfidenceTo = (confidence: Differential['confidence'], ceiling: Differential['confidence']): Differential['confidence'] => {
  const order: Record<Differential['confidence'], number> = { Low: 0, Moderate: 1, High: 2 }
  return order[confidence] <= order[ceiling] ? confidence : ceiling
}

const applyResponsePolicy = (issue: IssueRecord, confidence: Differential['confidence'], missing: string[]): Differential['confidence'] => {
  const policy = responsePolicyFor(issue)
  const rawCap = issue.photoOnlyMaxConfidence ?? policy?.photo_only_max_confidence
  if (typeof rawCap !== 'number' || !Number.isFinite(rawCap)) return confidence

  const cap = Math.max(0, Math.min(1, rawCap > 1 ? rawCap / 100 : rawCap))
  const capped = lowerConfidenceTo(confidence, confidenceAtCeiling(cap))

  if (capped !== confidence && !missing.includes('response policy limits photo-only confidence')) missing.push('response policy limits photo-only confidence')

  if (policy?.photo_can_confirm === false) {
    const required = policy.required_confirmation ?? []
    if (!required.length) {
      if (!missing.includes('non-visual confirmation required by issue confidence policy')) missing.push('non-visual confirmation required by issue confidence policy')
    } else {
      for (const item of required) {
        const label = `confirmation: ${item}`
        if (!missing.includes(label)) missing.push(label)
      }
    }
  }

  return capped
}

function numeric(value?: string) {
  if (!value) return undefined
  const parsed = Number.parseFloat(value.replace(/[^0-9.+-]/g, ''))
  return Number.isFinite(parsed) ? parsed : undefined
}

function historyContribution(issue: IssueRecord, context: GrowContext, history: GrowLogEntry[]) {
  if (!history.length) return { score: 0, signals: [] as string[] }
  let score = 0
  const signals: string[] = []
  const issueIndicators = new Set(issue.indicators.map(normalise))
  const recurring = new Set<string>()

  for (const entry of history) {
    for (const symptom of entry.symptoms ?? []) {
      if (issueIndicators.has(normalise(symptom)) && context.symptoms.some((current) => normalise(current) === normalise(symptom))) recurring.add(symptom)
    }
  }
  if (recurring.size) {
    score += Math.min(1.5, recurring.size * 0.5)
    signals.push(`${recurring.size} current symptom${recurring.size === 1 ? '' : 's'} also recorded in prior follow-up history`)
  }

  const sameDiagnosis = history.filter((entry) => entry.diagnosisIssueSlug === issue.slug)
  if (sameDiagnosis.some((entry) => entry.outcome === 'Worsening' || entry.outcome === 'Stable')) {
    score += 0.5
    signals.push('the same hypothesis was previously recorded and the case remained stable or worsened')
  }
  if (sameDiagnosis.some((entry) => entry.outcome === 'Resolved')) {
    score -= 0.75
    signals.push('this hypothesis was previously marked resolved, which weakens simple persistence as an explanation')
  }

  if (needsRootZoneChemistry(issue)) {
    const currentPh = numeric(context.ph)
    const previousPh = history.map((entry) => numeric(entry.ph)).filter((value): value is number => value !== undefined)
    if (currentPh !== undefined && previousPh.some((value) => Math.abs(value - currentPh) >= 0.6)) {
      score += 0.5
      signals.push('pH changed materially across the investigation history')
    }
    const currentEc = numeric(context.ec)
    const previousEc = history.map((entry) => numeric(entry.ec)).filter((value): value is number => value !== undefined)
    if (currentEc !== undefined && previousEc.some((value) => Math.abs(value - currentEc) >= 0.6)) {
      score += 0.5
      signals.push('EC/PPM changed materially across the investigation history')
    }
  }

  if (needsWateringContext(issue) && context.watering) {
    const changed = history.some((entry) => entry.watering && normalise(entry.watering) !== normalise(context.watering))
    if (changed) {
      score += 0.5
      signals.push('watering or substrate-moisture context changed during the case')
    }
  }

  return { score: Math.max(-1, Math.min(2, score)), signals }
}

export function rankDifferentials(records: IssueRecord[], context: GrowContext, evidence: EvidenceFile[], history: GrowLogEntry[] = []): Differential[] {
  const selected = new Set(context.symptoms.map(normalise))
  const indicatorFrequency = buildIndicatorFrequency(records)
  const hasRootView = evidence.some((item) => item.slot === 'root-crown')
  const hasUnderside = evidence.some((item) => item.slot === 'underside')
  const hasWholePlant = evidence.some((item) => item.slot === 'whole-plant')
  const hasCloseUp = evidence.some((item) => item.slot === 'close-up')

  const ranked = records.map((issue) => {
    const matched = issue.indicators.filter((indicator) => selected.has(normalise(indicator)))
    const contradictory = issue.exclusions.filter((indicator) => selected.has(normalise(indicator)))
    const supportingScore = matched.reduce((total, indicator) => total + indicatorSignalWeight(indicatorFrequency.get(normalise(indicator)) ?? 1), 0)
    const contradictionScore = contradictory.reduce((total, indicator) => total + Math.max(4, indicatorSignalWeight(indicatorFrequency.get(normalise(indicator)) ?? 1) + 1), 0)
    const historical = historyContribution(issue, context, history)
    let score = supportingScore - contradictionScore + historical.score

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
    if (needsRootZoneChemistry(issue) && !context.ph) missing.push('measured pH')
    if (needsRootZoneChemistry(issue) && !context.ec) missing.push('measured EC/PPM')
    if (needsWateringContext(issue) && !context.watering) missing.push('recent irrigation / substrate-moisture context')

    let confidence: Differential['confidence'] = score >= 10 && matched.length >= 3 && contradictory.length === 0 ? 'High' : score >= 5 && matched.length >= 2 ? 'Moderate' : 'Low'

    if (laboratoryBoundedCategories.has(issue.category)) confidence = 'Low'
    if (issue.category === 'Root pathogen' && !hasRootView) confidence = 'Low'
    if (issue.category === 'Mite') {
      if (!hasUnderside) confidence = 'Low'
      else if (microscopicMiteSlugs.has(issue.slug) && confidence === 'High') confidence = 'Moderate'
    }
    if (issue.category === 'Insect' && !hasUnderside && confidence === 'High') confidence = 'Moderate'
    if ((issue.category === 'Nutrient deficiency' || issue.category === 'Nutrient toxicity') && (!context.ph || !context.ec) && confidence === 'High') confidence = 'Moderate'
    if ((!hasWholePlant || !hasCloseUp) && confidence === 'High') confidence = 'Moderate'
    confidence = applyResponsePolicy(issue, confidence, missing)

    return { issue, confidence, score, supporting: matched, contradicting: contradictory, missing, historySignals: historical.signals } satisfies Differential
  }).filter((item) => item.score > 0).sort((a, b) => b.score - a.score).slice(0, 4)

  return ranked.map((item, index) => {
    let confidence = item.confidence
    const missing = [...item.missing]
    if (index > 0 && confidence === 'High') confidence = 'Moderate'
    if (index === 0 && ranked.length > 1) {
      const margin = item.score - ranked[1].score
      if (margin < 2) {
        if (confidence === 'High') confidence = 'Moderate'
        if (!missing.includes('additional discriminating evidence between the leading look-alikes')) missing.push('additional discriminating evidence between the leading look-alikes')
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
  } finally { URL.revokeObjectURL(url) }
}

export function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}
