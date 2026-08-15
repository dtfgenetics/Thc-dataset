import type { EvidenceFile, GrowContext } from '../types'

export interface AccuracySnapshot {
  score: number
  status: 'locked' | 'needs-review' | 'blocked'
  headline: string
  reasons: string[]
}

export function summarizeEvidenceAccuracy(evidence: EvidenceFile[], context: GrowContext): AccuracySnapshot {
  const reasons: string[] = []

  if (!evidence.length) {
    return {
      score: 0,
      status: 'blocked',
      headline: 'No benchmark-ready evidence yet',
      reasons: ['Add at least one clear image or video before scoring.'],
    }
  }

  let score = 18
  if (evidence.length >= 2) score += 15
  else reasons.push('Add a second reference view for better grounding.')

  if (evidence.some((item) => item.slot === 'whole-plant')) score += 17
  else reasons.push('Capture a whole-plant view.')

  if (evidence.some((item) => item.slot === 'close-up')) score += 20
  else reasons.push('Capture an affected-tissue close-up.')

  if (evidence.some((item) => item.slot === 'underside')) score += 10
  if (evidence.some((item) => item.slot === 'root-crown')) score += 10
  if (evidence.some((item) => item.slot === 'video')) score += 8

  const goodQualityCount = evidence.filter((item) => item.quality === 'good').length
  if (goodQualityCount > 0) score += Math.min(18, goodQualityCount * 8)
  else reasons.push('Assess image quality and re-take if detail is too soft.')

  if (context.symptoms.length >= 2) score += 10
  else reasons.push('Select at least two symptoms to anchor the ranking.')

  if (context.stage) score += 4
  if (context.ph && context.ec) score += 4
  if (context.watering) score += 3

  const clamped = Math.max(0, Math.min(100, score))
  const status: AccuracySnapshot['status'] = clamped >= 80 ? 'locked' : clamped >= 60 ? 'needs-review' : 'blocked'

  const headline = status === 'locked'
    ? 'Benchmark-ready evidence'
    : status === 'needs-review'
      ? 'Improving evidence quality'
      : 'Not ready for a confident match'

  if (!reasons.length && clamped >= 80) {
    reasons.push('High-resolution views and matched symptom context are present.')
  }

  return {
    score: clamped,
    status,
    headline,
    reasons: reasons.slice(0, 4),
  }
}
