import { describe, expect, it } from 'vitest'
import { categoryOrder, issues } from '../data/catalog'
import { hasResolvedDisplayMedia, isDisplayableMedia, resolvedDisplayMediaForIssue } from './media'

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
  if (!hasResolvedDisplayMedia(issue, issues)) score += 3
  if (issue.reviewStatus !== 'reviewed') score += 2
  return score
}

function report() {
  const categoryCoverage = categoryOrder.map((category) => {
    const categoryIssues = issues.filter((issue) => issue.category === category)
    const approvedImages = categoryIssues.flatMap((issue) => issue.media).filter(isDisplayableMedia).length
    const profilesWithVisualReferences = categoryIssues.filter((issue) => hasResolvedDisplayMedia(issue, issues)).length
    const target = targetByCategory[category] ?? 0
    return {
      category,
      records: categoryIssues.length,
      approvedImages,
      profilesWithVisualReferences,
      target,
      imageCoveragePercent: target ? Math.round((approvedImages / target) * 1000) / 10 : null,
      recordsWithoutApprovedImages: categoryIssues.filter((issue) => issue.media.filter(isDisplayableMedia).length === 0).length,
      recordsWithoutAnyVisualReference: categoryIssues.filter((issue) => !hasResolvedDisplayMedia(issue, issues)).length,
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
      resolvedVisualReferences: resolvedDisplayMediaForIssue(issue, issues).length,
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
    profilesWithVisualReferences: issues.filter((issue) => hasResolvedDisplayMedia(issue, issues)).length,
    withoutApprovedImages: issues.filter((issue) => issue.media.filter(isDisplayableMedia).length === 0).length,
    withoutAnyVisualReference: issues.filter((issue) => !hasResolvedDisplayMedia(issue, issues)).length,
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

  it('resolves verified multi-condition composites without duplicating assets', () => {
    const nitrogen = issues.find((issue) => issue.slug === 'nitrogen-deficiency')
    const copper = issues.find((issue) => issue.slug === 'copper-deficiency')
    expect(nitrogen).toBeTruthy()
    expect(copper).toBeTruthy()
    expect(nitrogen?.media.filter(isDisplayableMedia)).toHaveLength(1)
    expect(copper?.media.filter(isDisplayableMedia)).toHaveLength(0)
    expect(resolvedDisplayMediaForIssue(nitrogen!, issues)).toHaveLength(2)
    expect(resolvedDisplayMediaForIssue(copper!, issues)).toHaveLength(1)
  })

  it('counts only the licensed Japanese beetle morphology reference as displayable', () => {
    const record = issues.find((issue) => issue.slug === 'japanese-beetle-hemp')
    expect(record).toBeTruthy()
    expect(record?.media).toHaveLength(2)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(1)
    expect(record?.media.find((item) => item.reviewStatus === 'license-review')?.trainingEligible).toBe(false)
  })

  it('counts only the licensed Dectes specimen as displayable', () => {
    const record = issues.find((issue) => issue.slug === 'dectes-stem-borer')
    expect(record).toBeTruthy()
    expect(record?.media).toHaveLength(2)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(1)
    expect(record?.media.find((item) => item.mediaType === 'video')?.reviewStatus).toBe('license-review')
    expect(record?.media.find((item) => item.mediaType === 'video')?.trainingEligible).toBe(false)
  })

  it('keeps HLVd molecularly bounded and unlicensed field references out of display and training', () => {
    const record = issues.find((issue) => issue.slug === 'hop-latent-viroid')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.25)
    expect(record?.sources.some((source) => source.doi === '10.1080/07060661.2023.2279184')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.3390/plants14050830')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('extension.oregonstate.edu/catalog/em-9570'))).toBe(true)
    expect(confirmation).toContain('validated hlvd rt-pcr')
    expect(confirmation).toContain('paired root plus upper, middle, or lower foliage samples')
    expect(confirmation).toContain('keep unlinked, symptom-only, detached-leaf-only, and assay-panel-only captures out of the confirmed class')
    expect(warnings).toContain('infected plants may be asymptomatic')
    expect(warnings).toContain('one tissue or canopy position may test negative while another tests positive')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Normal late-flowering senescence or cultivar-specific fade',
      'Pythium, Fusarium, Rhizoctonia, or other root/crown disease',
      'Broad mite or hemp russet mite injury',
      'Beet curly top virus, phytoplasma, or another systemic pathogen',
    ]))
    expect(record?.media).toHaveLength(3)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(1)
    expect(record?.media.filter((item) => item.reviewStatus === 'license-review')).toHaveLength(2)
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
  })

  it('keeps Alternaria species labels organism-linked and records the open-media gap', () => {
    const record = issues.find((issue) => issue.slug === 'alternaria-leaf-spot')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.45)
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-01-21-0130-PDN')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1080/07060661.2021.1988712')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('pnwhandbooks.org/plantdisease'))).toBe(true)
    expect(confirmation).toContain('validated molecular identification from the sampled plant')
    expect(confirmation).toContain('keep symptom-only, detached-leaf-only, unlinked culture, mixed-organism, low-resolution, and stock/vendor/generated captures out of the confirmed alternaria class')
    expect(warnings).toContain('no image or video was added in this batch')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Septoria leaf spot',
      'Cercospora leaf spot',
      'Bipolaris leaf spot or blight',
      'Anthracnose / Colletotrichum leaf spot',
      'Bacterial leaf spot',
      'Spray or contact injury',
    ]))
    expect(record?.media).toHaveLength(0)
  })
})
