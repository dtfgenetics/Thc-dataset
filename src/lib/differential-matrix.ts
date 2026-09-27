import type { Differential, GrowContext } from '../types'

const normalise = (value: string) => value.trim().toLowerCase()

export interface DifferentialMatrixRow {
  slug: string
  name: string
  confidence: Differential['confidence']
  score: number
  supportCount: number
  contradictionCount: number
  missingCount: number
  support: string[]
  contradictions: string[]
  missing: string[]
  uniqueUnobservedIndicators: string[]
}

export interface DifferentialMatrix {
  rows: DifferentialMatrixRow[]
  leaderMargin: number | null
  separatingEvidence: string[]
}

export function buildDifferentialMatrix(results: Differential[], context: GrowContext, limit = 3): DifferentialMatrix {
  const selected = new Set(context.symptoms.map(normalise))
  const visible = results.slice(0, Math.max(1, limit))
  const rows = visible.map((candidate) => {
    const otherIndicators = new Set(
      visible
        .filter((other) => other.issue.slug !== candidate.issue.slug)
        .flatMap((other) => other.issue.indicators.map(normalise)),
    )
    const uniqueUnobservedIndicators = candidate.issue.indicators.filter((indicator) => {
      const key = normalise(indicator)
      return !selected.has(key) && !otherIndicators.has(key)
    }).slice(0, 3)

    return {
      slug: candidate.issue.slug,
      name: candidate.issue.name,
      confidence: candidate.confidence,
      score: candidate.score,
      supportCount: candidate.supporting.length,
      contradictionCount: candidate.contradicting.length,
      missingCount: candidate.missing.length,
      support: candidate.supporting.slice(0, 4),
      contradictions: candidate.contradicting.slice(0, 3),
      missing: candidate.missing.slice(0, 4),
      uniqueUnobservedIndicators,
    }
  })

  const leaderMargin = rows.length > 1 ? rows[0].score - rows[1].score : null
  const separatingEvidence = rows.flatMap((row) =>
    row.uniqueUnobservedIndicators.map((indicator) => `${row.name}: ${indicator}`),
  ).slice(0, 6)

  return { rows, leaderMargin, separatingEvidence }
}
