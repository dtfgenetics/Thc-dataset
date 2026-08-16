import { describe, expect, it } from 'vitest'
import { issues, supplementalIssues } from '../data/catalog'
import { isDisplayableMedia } from './media'

describe('supplemental diagnostic catalog quality gates', () => {
  it('keeps combined identifiers and slugs unique', () => {
    expect(new Set(issues.map((issue) => issue.id)).size).toBe(issues.length)
    expect(new Set(issues.map((issue) => issue.slug)).size).toBe(issues.length)
  })

  it('requires reviewed supplemental records to be source-backed and differential-ready', () => {
    for (const issue of supplementalIssues) {
      expect(issue.reviewStatus, `${issue.slug} must be reviewed before public catalog inclusion`).toBe('reviewed')
      expect(issue.sources.length, `${issue.slug} has no mapped source`).toBeGreaterThan(0)
      expect(issue.indicators.length, `${issue.slug} needs discriminating supporting signs`).toBeGreaterThanOrEqual(2)
      expect(issue.exclusions.length, `${issue.slug} needs explicit evidence-against rules`).toBeGreaterThanOrEqual(2)
      expect(issue.lookAlikes.length, `${issue.slug} needs realistic look-alikes`).toBeGreaterThanOrEqual(2)
      expect(issue.confirmation.length, `${issue.slug} needs confirmation guidance`).toBeGreaterThanOrEqual(2)
      expect(issue.immediateActions.length, `${issue.slug} needs safe immediate actions`).toBeGreaterThan(0)
      expect(issue.correctivePlan.length, `${issue.slug} needs a corrective plan`).toBeGreaterThan(0)
      expect(issue.prevention.length, `${issue.slug} needs prevention guidance`).toBeGreaterThan(0)
      expect(issue.warnings.length, `${issue.slug} needs overclaiming/safety warnings`).toBeGreaterThan(0)

      for (const source of issue.sources) {
        expect(source.url, `${issue.slug} source must use HTTPS`).toMatch(/^https:\/\//)
        expect(source.accessedDate, `${issue.slug} source needs an access date`).toMatch(/^\d{4}-\d{2}-\d{2}$/)
        expect(source.supportedClaims.length, `${issue.slug} source lacks claim mapping`).toBeGreaterThan(0)
      }
    }
  })

  it('publishes the publisher-verified rice root aphid DOI', () => {
    const issue = supplementalIssues.find((item) => item.slug === 'rice-root-aphid')
    const source = issue?.sources.find((item) => item.title === 'Cannabis sativa as a Host of Rice Root Aphid (Hemiptera: Aphididae) in North America')
    expect(source?.doi).toBe('10.1093/jipm/pmaa008')
    expect(source?.url).toBe('https://doi.org/10.1093/jipm/pmaa008')
    expect(source?.publicationDate).toBe('2020-07-20')
  })

  it('admits only fully verified reference media into supplemental profiles', () => {
    const permittedMediaSlugs = new Set(['rice-root-aphid', 'fusarium-crown-root-rot'])
    for (const issue of supplementalIssues) {
      if (!permittedMediaSlugs.has(issue.slug)) {
        expect(issue.media, `${issue.slug} should remain an explicit image gap until rights/provenance are verified`).toEqual([])
        continue
      }

      expect(issue.media.length, `${issue.slug} should have one verified promoted reference`).toBe(1)
      const media = issue.media[0]
      expect(media.sourceUrl).toMatch(/^https:\/\//)
      expect(media.url ?? media.thumbnailUrl).toMatch(/^https:\/\//)
      expect(media.creator).toBeTruthy()
      expect(media.license).toMatch(/CC BY/i)
      expect(media.requiredAttribution).toBeTruthy()
      expect(media.diagnosticLabel).toContain(issue.slug)
      expect(media.hostSpecies.toLowerCase()).toContain('cannabis')
      expect(media.hostContext).toBe('cannabis')
      expect(media.useLimitations.length).toBeGreaterThan(1)
      expect(media.displayPermission).toBe('permitted')
      expect(media.reviewStatus).toBe('approved-reference')
      expect(media.trainingPermission).toBe('permitted')
      expect(media.trainingEligible).toBe(false)
      expect(media.sha256).toMatch(/^[a-f0-9]{64}$/)
      expect(media.perceptualHash).toMatch(/^dhash64:[a-f0-9]{16}$/)
      expect(media.width).toBeGreaterThan(0)
      expect(media.height).toBeGreaterThan(0)
      expect(isDisplayableMedia(media)).toBe(true)
    }
  })

  it('keeps promoted supplemental media hashes unique', () => {
    const media = supplementalIssues.flatMap((issue) => issue.media)
    expect(new Set(media.map((item) => item.id)).size).toBe(media.length)
    expect(new Set(media.map((item) => item.sha256)).size).toBe(media.length)
    expect(new Set(media.map((item) => item.perceptualHash)).size).toBe(media.length)
  })

  it('keeps Fusarium laboratory-bounded and tied to the controlled policy', () => {
    const issue = supplementalIssues.find((item) => item.slug === 'fusarium-crown-root-rot')
    expect(issue?.canonicalId).toBe('CAN-ROOT-003')
    expect(issue?.responsePolicyId).toBe('POL-FUSARIUM')
    expect(issue?.photoOnlyMaxConfidence).toBe(0.5)
    expect(issue?.confirmation.join(' ').toLowerCase()).toMatch(/laboratory|isolation|molecular|sequence/)
    expect(issue?.warnings.join(' ').toLowerCase()).toMatch(/cannot confirm fusarium|without laboratory/)
    expect(issue?.media.every((item) => !item.trainingEligible)).toBe(true)
  })

  it('keeps salinity and drought measurement-bounded instead of image-defined', () => {
    const salinity = supplementalIssues.find((item) => item.slug === 'salinity-high-ec-stress')
    const drought = supplementalIssues.find((item) => item.slug === 'drought-water-deficit-stress')

    expect(salinity?.confirmation.join(' ').toLowerCase()).toMatch(/measure.*ec|root-zone.*ec/)
    expect(salinity?.warnings.join(' ').toLowerCase()).toMatch(/do not diagnose|must be measured|brown tips alone/)
    expect(drought?.confirmation.join(' ').toLowerCase()).toMatch(/measure.*root-zone|water content|moisture/)
    expect(drought?.warnings.join(' ').toLowerCase()).toMatch(/do not use one wilted photograph|one wilted photograph/)
  })

  it('separates above-ground cannabis aphid evidence from rice root aphid evidence', () => {
    const cannabisAphid = supplementalIssues.find((item) => item.slug === 'cannabis-aphid')
    const rootAphid = supplementalIssues.find((item) => item.slug === 'rice-root-aphid')

    expect(cannabisAphid?.affectedParts.join(' ').toLowerCase()).toMatch(/leaf|stem|petiole/)
    expect(cannabisAphid?.exclusions.join(' ').toLowerCase()).toMatch(/only roots contain aphids/)
    expect(rootAphid?.affectedParts.join(' ').toLowerCase()).toMatch(/root/)
    expect(rootAphid?.confirmation.join(' ').toLowerCase()).toMatch(/roots|root zone/)
  })
})
