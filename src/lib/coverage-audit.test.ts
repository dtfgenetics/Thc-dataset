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

  it('counts tarnished plant bug morphology media without promoting it to Cannabis ground truth', () => {
    const record = issues.find((issue) => issue.slug === 'tarnished-plant-bug')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''
    expect(record).toBeTruthy()
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.3)
    expect(record?.media).toHaveLength(1)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(1)
    expect(record?.media[0].hostContext).toBe('organism-only')
    expect(record?.media[0].trainingEligible).toBe(false)
    expect(confirmation).toContain('identify a captured adult or diagnostic later instar with an entomologist or validated regional key')
    expect(warnings).toContain('no licensed, plant-linked cannabis lygus injury image or verified diagnostic video was located for this batch')
  })

  it('counts licensed clomazone transfer references without promoting them to Cannabis ground truth', () => {
    const record = issues.find((issue) => issue.slug === 'herbicide-clomazone-bleaching-injury')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''
    expect(record).toBeTruthy()
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record?.media).toHaveLength(2)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(2)
    expect(record?.media.every((item) => item.hostContext === 'non-cannabis')).toBe(true)
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
    expect(confirmation).toContain('map affected and unaffected cannabis plants')
    expect(warnings).toContain('transfer references for color and field-edge context only')
  })

  it('keeps root-binding as a root-inspection diagnosis with bounded transfer media', () => {
    const record = issues.find((issue) => issue.slug === 'root-binding-container-stress')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record).toBeTruthy()
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record?.sources).toHaveLength(6)
    expect(record?.indicators.length).toBeGreaterThanOrEqual(6)
    expect(record?.exclusions.length).toBeGreaterThanOrEqual(8)
    expect(record?.lookAlikes.length).toBeGreaterThanOrEqual(12)
    expect(record?.confirmation.length).toBeGreaterThanOrEqual(7)
    expect(record?.media).toHaveLength(2)
    expect(record?.media.find((item) => item.id === 'media-pot-bound-root-mass-umd-reference-only')).toMatchObject({
      id: 'media-pot-bound-root-mass-umd-reference-only',
      hostContext: 'non-cannabis',
      displayPermission: 'not-permitted',
      trainingPermission: 'not-permitted',
      trainingEligible: false,
      view: 'root-crown',
      confirmation: 'illustrative',
    })
    expect(confirmation).toContain('extract the root ball intact')
    expect(confirmation).toContain('plant identity linked across dates')
    expect(warnings).toContain('reference metadata only')
  })

  it('keeps drought as a measured temporal diagnosis with bounded reference media', () => {
    const record = issues.find((issue) => issue.slug === 'drought-water-deficit-stress')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record).toBeTruthy()
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.25)
    expect(record?.sources).toHaveLength(6)
    expect(record?.indicators.length).toBeGreaterThanOrEqual(7)
    expect(record?.exclusions.length).toBeGreaterThanOrEqual(8)
    expect(record?.lookAlikes.length).toBeGreaterThanOrEqual(14)
    expect(record?.confirmation.length).toBeGreaterThanOrEqual(7)
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0].trainingEligible).toBe(false)
    expect(confirmation).toContain('before deficit, during the suspected event, immediately before rehydration, and after rehydration')
    expect(confirmation).toContain('root-zone ec and ph')
    expect(warnings).toContain('drought remains an exposure-linked diagnosis')
    expect(warnings).toContain('final-harvest, six-panel study composite rather than a longitudinal diagnostic sequence')
  })

  it('keeps salinity measured and composition-aware while bounding reference diagrams', () => {
    const record = issues.find((issue) => issue.slug === 'salinity-high-ec-stress')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''
    const primary = record?.sources.find((source) => source.doi === '10.3389/fpls.2020.01169')!
    expect(primary.accessedDate).toBe('2026-10-19')
    expect(primary.supportedClaims).toHaveLength(8)
    expect(primary.supportedClaims.join(' ')).toContain('4, 8, 10, 20 and 40 mM in aquaponic panel B')
    expect(primary.supportedClaims.join(' ')).not.toContain('matched hydroponic and aquaponic panels')
    expect(confirmation).toContain('flowering day separately from days since salt exposure')
    expect(record?.media.every((item) => item.useLimitations.join(' ').includes('not an identical low-dose comparison'))).toBe(true)

    expect(record).toBeTruthy()
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record?.sources).toHaveLength(5)
    expect(record?.sources.filter((source) => source.doi === '10.3389/fpls.2025.1433985')).toHaveLength(1)
    expect(record?.indicators.length).toBeGreaterThanOrEqual(8)
    expect(record?.exclusions.length).toBeGreaterThanOrEqual(8)
    expect(record?.lookAlikes.length).toBeGreaterThanOrEqual(14)
    expect(record?.confirmation.length).toBeGreaterThanOrEqual(8)
    expect(record?.media).toHaveLength(2)
    expect(record?.media.every((item) => item.view === 'diagram' && item.trainingEligible === false)).toBe(true)
    expect(confirmation).toContain('source-water analysis, sodium and chloride inputs')
    expect(confirmation).toContain('solution, substrate-extract, and tissue analysis')
    expect(warnings).toContain('same ec can be produced by nacl or by different nutrient mixtures')
    expect(warnings).toContain('neither is a symptom photograph, a plant-linked diagnostic sequence, or a verified diagnostic video')
  })

  it('counts only the licensed Dectes specimen as displayable', () => {
    const record = issues.find((issue) => issue.slug === 'dectes-stem-borer')
    const sampling = record?.sources.find((source) => source.url.includes('fs-1196'))
    expect(sampling?.publicationDate).toBe('2022-06')
    expect(sampling?.accessedDate).toBe('2026-10-19')
    expect(sampling?.supportedClaims).toHaveLength(5)
    expect(sampling?.supportedClaims.join(' ')).toContain('72% infested stems at the field edge versus 26%')
    expect(sampling?.supportedClaims.join(' ')).toContain('adult counts declined but stem infestation and lodging did not')
    expect(record?.confirmation.join(' ')).toContain('edge/interior position, distance, stem diameter, and total stems examined')
    expect(record?.confirmation.join(' ')).toContain('adult activity, dissected-stem infestation, and breakage/lodging as separate endpoints')
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
    const transmissionSource = record?.sources.find((source) => source.doi === '10.3390/plants14050830')
    expect(transmissionSource?.supportedClaims).toHaveLength(9)
    expect(transmissionSource?.supportedClaims.join(' ')).toContain('first root emergence')
    expect(transmissionSource?.supportedClaims.join(' ')).toContain('reverse which rooting group')
    expect(confirmation).toContain('cutting date and first-root-emergence date separately')
    expect(confirmation).toContain('all four cuttings were positive')
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

  it('keeps Alternaria species labels organism-linked and records the training-media gap', () => {
    const record = issues.find((issue) => issue.slug === 'alternaria-leaf-spot')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.25)
    expect(record?.name).toBe('Alternaria leaf spot complex')
    expect(record?.scientificName).toContain('A. cannabina')
    expect(record?.sources.some((source) => source.doi === '10.1007/s10658-021-02450-1')).toBe(true)
    expect(confirmation).toContain('its, gapdh, tef1, rpb2, and atpase')
    expect(confirmation).toContain('visible leaf injury, lesion-linked alternaria detection, and causally attributed disease as separate labels')
    expect(record?.exclusions.join(' ')).toContain('ITS-only match')
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-01-21-0130-PDN')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1080/07060661.2021.1988712')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('pnwhandbooks.org/plantdisease'))).toBe(true)
    expect(confirmation).toContain('validated molecular identification from the sampled plant')
    expect(confirmation).toContain('keep symptom-only, detached-leaf-only, unlinked culture, mixed-organism, low-resolution, and stock/vendor/generated captures out of the confirmed alternaria class')
    expect(warnings).toContain('two cc by 4.0 assay composites are reference-only')
    expect(warnings).toContain('panel-resolved training admission and independent field/video samples remain gaps')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Septoria leaf spot',
      'Cercospora leaf spot',
      'Bipolaris leaf spot or blight',
      'Anthracnose / Colletotrichum leaf spot',
      'Bacterial leaf spot',
      'Spray or contact injury',
    ]))
    expect(record?.media).toHaveLength(2)
  })

  it('keeps Cercospora labels multilocus-bounded, causal, and reference-media-safe', () => {
    const record = issues.find((issue) => issue.slug === 'cercospora-leaf-spot')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.3)
    expect(record?.indicators).toHaveLength(8)
    expect(record?.exclusions).toHaveLength(10)
    expect(record?.progression).toHaveLength(5)
    expect(record?.lookAlikes).toHaveLength(14)
    expect(record?.confirmation).toHaveLength(7)
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-01-19-0135-PDN')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-11-19-2287-PDN')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-05-25-0946-PDN')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.32473/edis-pp379-2024')).toBe(true)
    expect(confirmation).toContain('use validated multilocus evidence')
    expect(confirmation).toContain('symptom reproduction on cannabis, recovery of the same organism, and symptomless matched controls')
    expect(confirmation).toContain('keep symptom-only, detached-leaf-only, upper-surface-only, culture-unlinked, its-only, single-locus-only, mixed-pathogen, low-resolution, stock, vendor, forum, generated, and rights-unclear samples out')
    expect(warnings).toContain('study-specific observations, not universal timing, severity, cultivar, yield, or action thresholds')
    expect(warnings).toContain('institutional differential, not a lesion-linked laboratory record')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Septoria leaf spot complex',
      'Pseudocercospora olive or sooty leaf spot',
      'Curvularia leaf spot',
      'Bipolaris leaf spot or blight',
      'Anthracnose / Colletotrichum leaf spot',
      'Bacterial leaf spot or blight',
      'Spray, droplet, light, nutrient, salinity, or water-stress injury',
    ]))
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0].trainingPermission).toBe('not-permitted')
    expect(record?.media[0].trainingEligible).toBe(false)
  })

  it.each([['zinc-deficiency', 0.15], ['manganese-deficiency', 0.15], ['sulfur-deficiency', 0.20]] as const)('bounds %s visual labels by linked analytical evidence', (slug, ceiling) => {
    const record = issues.find((issue) => issue.slug === slug)
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(ceiling)
    expect(record?.confirmation.join(' ')).toContain('persistent plant and leaf-sample identifier')
    expect(record?.confirmation.join(' ')).toContain('causally attributed injury as separate labels')
    expect(record?.exclusions.join(' ')).toContain('universal diagnostic threshold')
    expect(record?.media.every((media) => !media.trainingEligible)).toBe(true)
  })

  it('bounds copper image labels to specimen-linked analytical evidence', () => {
    const record = issues.find((issue) => issue.slug === 'copper-deficiency')
    const confirmation = record?.confirmation.join(' ') ?? ''
    const exclusions = record?.exclusions.join(' ') ?? ''
    const warnings = record?.warnings.join(' ') ?? ''

    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.sources.some((source) => source.doi === '10.3390/app9204432')).toBe(true)
    expect(confirmation).toContain('persistent plant and leaf-sample identifier')
    expect(confirmation).toContain('causally attributed copper injury as separate labels')
    const excessSource = record?.sources.find((source) => source.doi === '10.3390/environments8110111')
    expect(excessSource?.supportedClaims).toHaveLength(6)
    expect(excessSource?.supportedClaims.join(' ')).toContain('hydroponically')
    expect(record?.lookAlikes).toContain('Copper excess or contaminated-medium exposure')
    expect(confirmation).toContain('SPAD leaf, shoot digest and root digest')
    expect(warnings).toContain('does not demonstrate a sulfate rescue')
    expect(exclusions).toContain('universal diagnostic threshold')
    expect(warnings).toContain('not a measured diagnostic-accuracy estimate')
    expect(record?.media).toEqual([])
  })

  it('bounds boron-toxicity images to exposure- and specimen-linked evidence', () => {
    const record = issues.find((issue) => issue.slug === 'boron-toxicity')
    const confirmation = record?.confirmation.join(' ') ?? ''
    const exclusions = record?.exclusions.join(' ') ?? ''
    const warnings = record?.warnings.join(' ') ?? ''

    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.sources.map((source) => source.doi)).toContain('10.3390/app9204432')
    expect(confirmation).toContain('persistent plant and leaf-sample identifier')
    expect(confirmation).toContain('causally attributed boron injury as separate labels')
    expect(confirmation).toContain('full two-class Figure 5 composite out of automated training')
    const ionSource = record?.sources.find((source) => source.url === 'https://ipm.ucanr.edu/home-and-landscape/boron-toxicity-or-other-specific-ions-in-excess/')
    expect(ionSource?.supportedClaims).toHaveLength(3)
    expect(ionSource?.supportedClaims.join(' ')).toContain('overall EC or TDS remains acceptable')
    expect(record?.progression.find((step) => step.stage === 'Specific-ion measurement limit')?.description).toContain('Acceptable EC or TDS cannot exclude excess boron')
    expect(record?.progression.find((step) => step.stage === 'Comparison-sample separation')?.description).toContain('Do not pool healthy and affected tissues')
    expect(record?.progression.find((step) => step.stage === 'Comparison-sample separation')?.description).toContain('not Cannabis thresholds')
    expect(exclusions).toContain('universal threshold')
    expect(warnings).toContain('not a measured diagnostic-accuracy estimate')
    expect(record?.media.every((media) => !media.trainingEligible)).toBe(true)
  })

  it('bounds phosphorus images to specimen-linked analytical evidence', () => {
    const record = issues.find((issue) => issue.slug === 'phosphorus-deficiency')
    const confirmation = record?.confirmation.join(' ') ?? ''
    const exclusions = record?.exclusions.join(' ') ?? ''
    const warnings = record?.warnings.join(' ') ?? ''
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.sources.map((source) => source.doi)).toEqual(expect.arrayContaining(['10.3390/app9204432', '10.3389/fpls.2021.764103']))
    expect(confirmation).toContain('persistent plant and leaf-sample identifier')
    expect(confirmation).toContain('causally attributed phosphorus injury as separate labels')
    expect(confirmation).toContain('full three-class Figure 2 composite out of automated training')
    expect(exclusions).toContain('universal diagnostic threshold')
    expect(warnings).toContain('not a measured diagnostic-accuracy estimate')
    expect(record?.media.every((media) => !media.trainingEligible)).toBe(true)
  })

  it('bounds potassium images to specimen-linked analytical evidence', () => {
    const record = issues.find((issue) => issue.slug === 'potassium-deficiency')
    const confirmation = record?.confirmation.join(' ') ?? ''
    const exclusions = record?.exclusions.join(' ') ?? ''
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.sources.map((source) => source.doi)).toEqual(expect.arrayContaining(['10.3390/app9204432', '10.3390/plants12030422']))
    expect(confirmation).toContain('persistent plant and leaf-sample identifier')
    expect(confirmation).toContain('causally attributed potassium injury as separate labels')
    expect(confirmation).toContain('full three-class vegetative Figure 3 composite')
    expect(confirmation).toContain('four-panel flowering Figure 4 composite out of automated training')
    expect(exclusions).toContain('universal diagnostic threshold')
    expect(record?.media.every((media) => !media.trainingEligible)).toBe(true)
  })

  it('bounds magnesium images to specimen-linked analytical evidence', () => {
    const record = issues.find((issue) => issue.slug === 'magnesium-deficiency')
    const confirmation = record?.confirmation.join(' ') ?? ''
    const exclusions = record?.exclusions.join(' ') ?? ''
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.sources.map((source) => source.doi)).toEqual(expect.arrayContaining(['10.3390/app9204432', '10.3390/plants12030422']))
    expect(confirmation).toContain('persistent plant and leaf-sample identifier')
    expect(confirmation).toContain('causally attributed magnesium injury as separate labels')
    expect(confirmation).toContain('full three-class vegetative Figure 3 composite')
    expect(confirmation).toContain('five-panel flowering Figure 6 composite out of automated training')
    expect(exclusions).toContain('universal diagnostic threshold')
    expect(record?.media.every((media) => !media.trainingEligible)).toBe(true)
  })

  it('bounds calcium images to specimen-linked supply and transport evidence', () => {
    const record = issues.find((issue) => issue.slug === 'calcium-deficiency')
    const confirmation = record?.confirmation.join(' ') ?? ''
    const exclusions = record?.exclusions.join(' ') ?? ''
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.sources.map((source) => source.doi)).toEqual(expect.arrayContaining(['10.3390/app9204432', '10.3390/plants12030422']))
    expect(confirmation).toContain('persistent plant and leaf-sample identifier')
    expect(confirmation).toContain('causally attributed calcium injury as separate labels')
    expect(exclusions).toContain('universal diagnostic threshold')
    expect(exclusions).toContain('transport-limited injury')
    expect(record?.media.every((media) => !media.trainingEligible)).toBe(true)
  })

  it('bounds nitrogen-toxicity images to exposure- and mechanism-linked evidence', () => {
    const record = issues.find((issue) => issue.slug === 'nitrogen-toxicity')
    const confirmation = record?.confirmation.join(' ') ?? ''
    const exclusions = record?.exclusions.join(' ') ?? ''
    const warnings = record?.warnings.join(' ') ?? ''
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.sources.map((source) => source.doi)).toEqual(expect.arrayContaining(['10.3389/fpls.2020.572293', '10.3389/fpls.2022.830224']))
    expect(confirmation).toContain('persistent plant and leaf-sample identifier')
    expect(confirmation).toContain('causally attributed nitrogen injury as separate labels')
    expect(confirmation).toContain('fifteen-panel Figure 1 dose-and-organ composite')
    expect(exclusions).toContain('universal diagnostic threshold')
    expect(exclusions).toContain('Excessive total-nitrogen dose and excessive ammonium fraction')
    const nitrogenForm = record?.sources.find((source) => source.doi === '10.3389/fpls.2022.830224')
    expect(nitrogenForm?.supportedClaims).toHaveLength(13)
    expect(nitrogenForm?.supportedClaims.join(' ')).toContain('nitrate-only plants developed dotted marginal chlorosis')
    expect(nitrogenForm?.supportedClaims.join(' ')).toContain('residual coconut fiber')
    expect(record?.progression.find((step) => step.stage === 'Root-material exclusion check')?.description).toContain('Separate attached medium')
    expect(record?.progression.find((step) => step.stage === 'Endpoint and intervention timing')?.description).toContain('not relabel the study as a withdrawal-rescue trial')
    expect(record?.progression.find((step) => step.stage === 'Input-versus-leachate comparison')?.description).toContain('not a universally symptom-free image class')
    expect(warnings).toContain('not a measured diagnostic-accuracy estimate')
    expect(record?.media.every((media) => !media.trainingEligible)).toBe(true)
  })

  it('keeps late-cycle yellowing separate from healthy-control and maturity labels', () => {
    const record = issues.find((issue) => issue.slug === 'normal-late-flower-fade')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record?.sources.some((source) => source.doi === '10.3390/plants12030422')).toBe(true)
    expect(record?.indicators.join(' ')).toContain('adequately nourished control')
    expect(record?.confirmation.join(' ')).toContain('persistent plant and leaf identifiers')
    expect(record?.confirmation.join(' ')).toContain('not a negative nutrient or pathogen assay')
    expect(record?.warnings.join(' ')).toContain('do not establish a harvest window')
    const maturitySource = record?.sources.find((source) => source.doi === '10.3390/plants14101532')
    expect(maturitySource?.supportedClaims).toHaveLength(3)
    expect(maturitySource?.supportedClaims.join(' ')).toContain('genotypes 11, 13, and 15 peaked earlier')
    expect(maturitySource?.supportedClaims.join(' ')).toContain('white trichomes contaminating stigma masks')
    expect(record?.progression.find((step) => step.stage === 'Organ-specific maturity comparison')?.description).toContain('different harvested flowers a same-flower video timeline')
    expect(record?.progression.find((step) => step.stage === 'Segmentation and confirmation check')?.description).toContain('not calibrated smartphone cutoffs')
    expect(record?.media).toHaveLength(2)
    expect(record?.media[0]?.view).toBe('diagram')
    expect(record?.media[0]?.trainingEligible).toBe(false)
  })

  it('bounds iron image labels and preserves symptom-negative analytical evidence', () => {
    const record = issues.find((issue) => issue.slug === 'iron-deficiency')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.confirmation.join(' ')).toContain('persistent plant and leaf-sample identifier')
    expect(record?.confirmation.join(' ')).toContain('a normal-looking photograph is not a negative iron assay')
    expect(record?.warnings.join(' ')).toContain('do not isolate which factor')
    expect(record?.sources.map((source) => source.doi)).toEqual(expect.arrayContaining(['10.3390/app9204432', '10.3390/plants12030422']))
    expect(record?.media.every((media) => !media.trainingEligible)).toBe(true)
  })

  it('keeps root-knot species labels organism-linked and the composite root reference out of training', () => {
    const record = issues.find((issue) => issue.slug === 'root-knot-nematodes')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record?.sources.some((source) => source.doi === '10.21307/jofnem-2022-002')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.2478/jofnem-2024-0003')).toBe(true)
    expect(confirmation).toContain('persistent root-specimen identifier')
    expect(warnings).toContain('visible gall burden cannot substitute for organism counts')
    expect(record?.sources.some((source) => source.doi === '10.21307/jofnem-2021-052')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.3390/plants14020227')).toBe(true)
    expect(confirmation).toContain('adult-female and juvenile morphology')
    expect(confirmation).toContain('species-specific pcr or sequence assay')
    expect(confirmation).toContain('keep canopy-only, symptom-only, detached-root-only, unlinked soil/root assay, species-from-gall, low-resolution, stock, forum, vendor, or generated captures out of the confirmed root-knot class')
    expect(warnings).toContain('do not identify species or race')
    expect(warnings).toContain('seed-extract bioassays rather than infected-root symptoms')
    const virulenceSource = record?.sources.find((source) => source.doi === '10.3390/plants14020227')
    expect(virulenceSource?.accessedDate).toBe('2026-10-18')
    expect(virulenceSource?.supportedClaims).toHaveLength(7)
    const virulenceClaims = virulenceSource?.supportedClaims.join(' ').toLowerCase() ?? ''
    expect(virulenceClaims).toContain('30-day greenhouse endpoint at 25–29 °c')
    expect(virulenceClaims).toContain('destructive microscopy counts are not equivalent to gall counts')
    expect(virulenceClaims).toContain('three endpoints have different denominators')
    expect(confirmation).toContain('staining and destructive preparation')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Normal lateral-root branch points or root primordia',
      'Root binding / circling roots',
      'Pythium or other oomycete root rot',
      'Rhizoctonia root rot / sore shin',
      'Fusarium root or crown disease',
      'Root-zone hypoxia / overwatering',
      'High EC / fertilizer salt injury',
    ]))
    expect(record?.media).toHaveLength(1)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(1)
    expect(record?.media[0].license).toBe('CC BY 4.0')
    expect(record?.media[0].sourceUrl).toBe('https://doi.org/10.5281/zenodo.11644653')
    expect(record?.media[0].trainingPermission).toBe('permitted')
    expect(record?.media[0].trainingEligible).toBe(false)
  })

  it('keeps Pseudocercospora lab-bounded and mixed CC BY figures out of training', () => {
    const record = issues.find((issue) => issue.slug === 'pseudocercospora-olive-sooty-leaf-spot')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.4)
    expect(record?.sources.some((source) => source.doi === '10.3390/horticulturae9121261')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('pnwhandbooks.org/plantdisease'))).toBe(true)
    const primary = record?.sources.find((source) => source.doi === '10.3390/horticulturae9121261')!
    expect(primary.accessedDate).toBe('2026-10-18')
    expect(primary.supportedClaims).toHaveLength(12)
    expect(primary.supportedClaims.join(' ')).toContain('35 to 60 by 3.5 to 5 micrometers')
    expect(confirmation).toContain('mounting medium, objective, calibration and isolate linkage')
    expect(confirmation).toContain('unresolved length-unit discrepancy')
    const submission = record?.sources.find((source) => source.url === 'https://plantclinic.cornell.edu/services/collection-tips/')!
    expect(submission.accessedDate).toBe('2026-10-16')
    expect(submission.supportedClaims).toHaveLength(3)
    expect(submission.supportedClaims.join(' ')).toContain('not a Pseudocercospora-specific test')
    expect(submission.supportedClaims.join(' ')).toContain('Dataset inference')
    expect(confirmation).toContain('living/dead tissue margins')
    expect(confirmation).toContain('plant/lesion/submission ids')
    expect(confirmation).toContain('wet-box experimental images are not a template for sample shipment')
    expect(primary.supportedClaims.join(' ')).toContain('Table 1 lists tef as unavailable for both')
    expect(primary.supportedClaims.join(' ')).toContain('ITS OR101673, act OR344083 and rpb2 OR344085')
    expect(primary.supportedClaims.join(' ')).toContain('ITS OR101674, act OR344084 and rpb2 OR344086')
    expect(primary.supportedClaims.join(' ')).toContain('only SDBR-CMU372 was included')
    expect(confirmation).toContain('record tef as unavailable')
    expect(confirmation).toContain('thirty-five days describes fungal colonies')
    expect(confirmation).toContain('not four-locus reconfirmation')
    expect(confirmation).toContain('its plus act, tef1, and rpb2')
    expect(confirmation).toContain('keep symptom-only, upper-surface-only, detached-leaf-only, mixed-pathogen, unlinked-laboratory, low-resolution, and stock/vendor/forum/generated captures out of the confirmed pseudocercospora class')
    expect(warnings).toContain('twenty symptomatic leaves and two isolates from one thailand plantation')
    expect(warnings).toContain('mixed composites')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Cercospora leaf spot',
      'Septoria leaf spot',
      'Downy mildew / Pseudoperonospora',
      'Two-spotted spider mite injury',
      'Spray, contact, or light injury',
    ]))
    expect(record?.media).toHaveLength(2)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(2)
    expect(record?.media.every((item) => item.license === 'CC BY 4.0')).toBe(true)
    expect(record?.media.every((item) => item.trainingPermission === 'permitted')).toBe(true)
    expect(record?.media.every((item) => item.trainingEligible === false)).toBe(true)
    expect(record?.media.every((item) => item.confirmation === 'lab-confirmed')).toBe(true)
    const natural = record?.media.find((item) => item.id === 'media-pseudocercospora-cannabis-figure-1-ccby4')!
    const assay = record?.media.find((item) => item.id === 'media-pseudocercospora-cannabis-figure-2-pathogenicity-ccby4')!
    expect(natural.useLimitations.join(' ')).toContain('not leaf-level dimensions')
    expect(assay.useLimitations.join(' ')).toContain('do not silently substitute micrometers')
  })

  it('keeps downy mildew organism-linked and rights-unclear symptom references out of display and training', () => {
    const record = issues.find((issue) => issue.slug === 'downy-mildew-pseudoperonospora')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''
    const firstReport = record?.sources.find((source) => source.doi === '10.1094/PDIS-08-22-1930-PDN')!
    const resistance = record?.sources.find((source) => source.doi === '10.1094/PDIS-09-25-1916-RE')!
    expect(firstReport.accessedDate).toBe('2026-10-18')
    expect(firstReport.publicationDate).toBe('2023-05-16')
    expect(firstReport.supportedClaims).toHaveLength(6)
    expect(firstReport.supportedClaims.join(' ')).toContain('19 degrees C')
    expect(firstReport.supportedClaims.join(' ')).toContain('not axenic agar culture')
    expect(resistance.publicationDate).toBe('2026-09-08')
    expect(resistance.accessedDate).toBe('2026-10-21')
    expect(resistance.supportedClaims.join(' ')).toContain('final publisher abstract')
    const version = record?.sources.find((source) => source.url.includes('seqNo115=428781'))
    expect(version?.supportedClaims.join(' ')).toContain('detached-leaf')
    expect(warnings).toContain('source-version conflict')
    expect(confirmation).toContain('paired scores on the same identified disc')
    expect(confirmation).toContain('inoculum concentration rather than a measured deposited dose')
    expect(confirmation).toContain('host-tissue recovery substrate')

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.35)
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-08-22-1930-PDN')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-09-25-1916-RE')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('onspecialtycrops.ca/2021/07/21'))).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('ag.purdue.edu/hemp-project/diseases'))).toBe(true)
    expect(confirmation).toContain('its, cox2, and ypt1')
    expect(confirmation).toContain('midday negative')
    expect(confirmation).toContain('keep symptom-only, upper-surface-only, midday-underside-only, detached-stock-photo, mixed-pathogen, unlinked-laboratory, low-resolution, forum, vendor, or generated captures out of the confirmed downy-mildew class')
    expect(warnings).toContain('leaf-disc, detached-leaf, visual, and cnn phenotyping methods')
    expect(warnings).toContain('lack explicit reusable or automated-training rights')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Septoria leaf spot',
      'Pseudocercospora olive or sooty leaf spot',
      'Rust',
      'Powdery mildew',
      'Spray, contact, or droplet injury',
    ]))
    expect(record?.media).toHaveLength(2)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(0)
    expect(record?.media.every((item) => item.reviewStatus === 'license-review')).toBe(true)
    expect(record?.media.every((item) => item.trainingPermission === 'not-permitted')).toBe(true)
    expect(record?.media.every((item) => item.trainingEligible === false)).toBe(true)
  })

  it('keeps Serratia species labels laboratory-linked and generic bacterial imagery out of display and training', () => {
    const record = issues.find((issue) => issue.slug === 'serratia-marcescens-leaf-spot')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.3)
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-04-19-0782-PDN')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1094/PHP-03-20-0017-RS')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('plantpathology.ces.ncsu.edu/news/exserohilum'))).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('canada.ca/en/public-health/services/laboratory-biosafety'))).toBe(true)
    expect(confirmation).toContain('16s rrna and rpob')
    expect(confirmation).toContain('do not identify serratia from pink or red pigment alone')
    expect(confirmation).toContain('keep symptom-only, angular-lesion-only, red-ooze-only, detached-leaf, mixed-pathogen, unlinked-laboratory, low-resolution, stock, forum, vendor, or generated captures out of the confirmed serratia class')
    expect(warnings).toContain('greenhouse-bound and included cultivar carmagnola')
    expect(warnings).toContain('generic bacterial leaf spot/blight differential')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Xanthomonas bacterial leaf spot',
      'Exserohilum / Helminthosporium leaf blight',
      'Septoria leaf spot',
      'Downy mildew / Pseudoperonospora',
      'Contact spray, droplet, or mechanical injury',
    ]))
    expect(record?.media).toHaveLength(1)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(0)
    expect(record?.media[0].reviewStatus).toBe('license-review')
    expect(record?.media[0].trainingPermission).toBe('not-permitted')
    expect(record?.media[0].trainingEligible).toBe(false)
  })

  it('bounds extreme substrate-pH labels to linked root-zone and specimen evidence', () => {
    const record = issues.find((issue) => issue.slug === 'acidic-extreme-substrate-ph-stress')
    const confirmation = record?.confirmation.join(' ') ?? ''
    const exclusions = record?.exclusions.join(' ') ?? ''
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.indicators).toHaveLength(8)
    expect(record?.exclusions).toHaveLength(10)
    expect(record?.confirmation).toHaveLength(12)
    expect(record?.confirmation.at(-1)).toContain('exchangeable-acidity method')
    expect(record?.sources.map((source) => source.doi)).toContain('10.1002/agg2.70044')
    expect(record?.sources.map((source) => source.url)).toContain('https://ag.purdue.edu/department/hla/extension/extension-publications-library/ext-pubs/ho-237-w.html')
    expect(confirmation).toContain('persistent plant, root-zone sample, root specimen, and leaf-tissue identifiers')
    expect(confirmation).toContain('do not compare PourThru, saturated-media-extract, 1:2 dilution')
    expect(confirmation).toContain('causally attributed pH stress')
    const pHSource = record?.sources.find((source) => source.doi === '10.1002/agg2.70044')
    expect(pHSource?.accessedDate).toBe('2026-10-16')
    expect(pHSource?.supportedClaims).toHaveLength(14)
    expect(pHSource?.supportedClaims.join(' ')).toContain('four cultivars across separate experiments: Baox, T1, Cherry Wine, and Sweetened')
    expect(pHSource?.supportedClaims.join(' ')).toContain('not an isolated iron challenge')
    expect(pHSource?.supportedClaims.join(' ')).toContain('Its leaf assays are not root assays')
    expect(record?.progression.find((step) => step.stage === 'Leaf-age assay linkage')?.description).toContain('do not assign an upper-leaf result to a lower-leaf photograph')
    expect(record?.progression.find((step) => step.stage === 'Bronzing attribution check')?.description).toContain('iron-specific causality as separate labels')
    expect(exclusions).toContain('universal diagnostic threshold')
    expect(exclusions).toContain('generic nutrient-availability chart')
    expect(record?.media).toEqual([])
  })

  it('bounds root-binding labels to intact plant-linked root evidence', () => {
    const record = issues.find((issue) => issue.slug === 'root-binding-container-stress')
    const confirmation = record?.confirmation.join(' ') ?? ''
    const exclusions = record?.exclusions.join(' ') ?? ''
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.15)
    expect(record?.indicators).toHaveLength(8)
    expect(record?.exclusions).toHaveLength(11)
    expect(record?.confirmation).toHaveLength(12)
    const volumeStudy = record?.sources.find((source) => source.doi === '10.1071/FP12049')
    expect(volumeStudy?.accessedDate).toBe('2026-10-19')
    expect(volumeStudy?.publicationDate).toBe('2012-06-15')
    expect(volumeStudy?.supportedClaims).toHaveLength(5)
    expect(volumeStudy?.supportedClaims.join(' ')).toContain('barley and sugar beet')
    expect(volumeStudy?.supportedClaims.join(' ')).toContain('not Cannabis diagnostic thresholds')
    expect(volumeStudy?.supportedClaims.join(' ')).toContain('finest roots could go undetected')
    expect(confirmation).toContain('resolution and segmentation masks')
    const repotting = record?.sources.find((source) => source.url.includes('/repotting-container-plants-for-long-term-health/'))
    expect(repotting?.publicationDate).toBe('2026-08-18')
    expect(repotting?.supportedClaims).toHaveLength(3)
    expect(repotting?.supportedClaims.join(' ')).toContain('not Cannabis treatment standards')
    expect(record?.progression.some((step) => step.stage === 'Post-repotting confounder')).toBe(true)
    expect(confirmation).toContain('not a laboratory-negative pathogen result')
    expect(exclusions).toContain('excess wet medium')
    expect(record?.sources.map((source) => source.doi)).toEqual(expect.arrayContaining(['10.1094/PHP-03-20-0017-RS', '10.1071/FP12049']))
    expect(confirmation).toContain('persistent plant and root-specimen identifiers')
    expect(confirmation).toContain('causally attributed container-restriction injury as separate labels')
    expect(exclusions).toContain('universal Cannabis diagnostic threshold')
    expect(record?.media).toHaveLength(2)
    expect(record?.media.find((item) => item.id === 'media-pot-bound-root-mass-umd-reference-only')).toMatchObject({
      id: 'media-pot-bound-root-mass-umd-reference-only',
      hostContext: 'non-cannabis',
      displayPermission: 'not-permitted',
      trainingPermission: 'not-permitted',
      trainingEligible: false,
    })
  })
})
