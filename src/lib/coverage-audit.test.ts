import { describe, expect, it } from 'vitest'
import { categoryOrder, issues } from '../data/issues'
import { isDisplayableMedia } from './media'

const targetByCategory: Partial<Record<(typeof categoryOrder)[number], number>> = {
  'Nutrient deficiency': 144,
  'Nutrient toxicity': 120,
  Insect: 105,
  Mite: 90,
  'Fungal pathogen': 105,
  'Bacterial pathogen': 45,
  'Root pathogen': 60,
  Viroid: 30,
  Virus: 30,
  'Phytoplasma / Spiroplasma': 15,
  'Genetic / developmental': 72,
  'Environmental stress': 70,
  'Water / root-zone': 60,
  'Normal development': 25,
  'Insufficient evidence': 125,
}

const weaknessScore = (issue: (typeof issues)[number]) => {
  let score = 0
  if (issue.sources.length === 0) score += 8
  if (issue.indicators.length < 2) score += 5
  if (issue.exclusions.length < 2) score += 4
  if (issue.lookAlikes.length < 2) score += 4
  if (issue.confirmation.length < 2) score += 5
  if (issue.media.filter(isDisplayableMedia).length === 0) score += 3
  if (issue.reviewStatus !== 'reviewed') score += 2
  return score
}

function report() {
  const categoryCoverage = categoryOrder.map((category) => {
    const categoryIssues = issues.filter((issue) => issue.category === category)
    const approvedImages = categoryIssues.flatMap((issue) => issue.media).filter(isDisplayableMedia).length
    const target = targetByCategory[category] ?? 0
    return {
      category,
      records: categoryIssues.length,
      approvedImages,
      target,
      imageCoveragePercent: target ? Math.round((approvedImages / target) * 1000) / 10 : null,
      recordsWithoutApprovedImages: categoryIssues.filter((issue) => issue.media.filter(isDisplayableMedia).length === 0).length,
      recordsWithoutSources: categoryIssues.filter((issue) => issue.sources.length === 0).length,
      recordsWithWeakIndicators: categoryIssues.filter((issue) => issue.indicators.length < 2).length,
      recordsWithWeakExclusions: categoryIssues.filter((issue) => issue.exclusions.length < 2).length,
      recordsWithWeakLookAlikes: categoryIssues.filter((issue) => issue.lookAlikes.length < 2).length,
      recordsWithWeakConfirmation: categoryIssues.filter((issue) => issue.confirmation.length < 2).length,
    }
  })

  const weakestProfiles = [...issues]
    .map((issue) => ({
      slug: issue.slug,
      name: issue.name,
      category: issue.category,
      reviewStatus: issue.reviewStatus,
      weaknessScore: weaknessScore(issue),
      indicators: issue.indicators.length,
      exclusions: issue.exclusions.length,
      lookAlikes: issue.lookAlikes.length,
      confirmation: issue.confirmation.length,
      sources: issue.sources.length,
      approvedImages: issue.media.filter(isDisplayableMedia).length,
      canonicalId: issue.canonicalId ?? null,
      responsePolicyId: issue.responsePolicyId ?? null,
    }))
    .sort((a, b) => b.weaknessScore - a.weaknessScore || a.name.localeCompare(b.name))
    .slice(0, 30)

  const totals = {
    records: issues.length,
    reviewed: issues.filter((issue) => issue.reviewStatus === 'reviewed').length,
    sourced: issues.filter((issue) => issue.sources.length > 0).length,
    approvedImages: issues.flatMap((issue) => issue.media).filter(isDisplayableMedia).length,
    withoutApprovedImages: issues.filter((issue) => issue.media.filter(isDisplayableMedia).length === 0).length,
    withoutSources: issues.filter((issue) => issue.sources.length === 0).length,
    weakIndicators: issues.filter((issue) => issue.indicators.length < 2).length,
    weakExclusions: issues.filter((issue) => issue.exclusions.length < 2).length,
    weakLookAlikes: issues.filter((issue) => issue.lookAlikes.length < 2).length,
    weakConfirmation: issues.filter((issue) => issue.confirmation.length < 2).length,
    withCanonicalId: issues.filter((issue) => Boolean(issue.canonicalId)).length,
    withResponsePolicyId: issues.filter((issue) => Boolean(issue.responsePolicyId)).length,
  }

  return { totals, categoryCoverage, weakestProfiles }
}

describe('diagnostic coverage audit', () => {
  it('emits a machine-readable coverage snapshot for portfolio QA', () => {
    const snapshot = report()
    console.log(`THC_COVERAGE_AUDIT_JSON=${JSON.stringify(snapshot)}`)
    expect(snapshot.totals.records).toBeGreaterThan(0)
    expect(snapshot.totals.sourced).toBeGreaterThan(0)
  })
})
