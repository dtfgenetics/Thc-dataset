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
    const permittedMediaCounts = new Map([
      ['rice-root-aphid', 1],
      ['fusarium-crown-root-rot', 1],
      ['cannabis-aphid', 1],
      ['root-knot-nematodes', 1],
      ['pseudocercospora-olive-sooty-leaf-spot', 2],
    ])
    for (const issue of supplementalIssues) {
      if (issue.slug === 'herbicide-clomazone-bleaching-injury') {
        expect(issue.media).toHaveLength(2)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(2)
        expect(issue.media.every((item) => item.hostContext === 'non-cannabis')).toBe(true)
        expect(issue.media.every((item) => item.license === 'CC BY-NC-SA 4.0')).toBe(true)
        expect(issue.media.every((item) => item.trainingPermission === 'not-permitted')).toBe(true)
        expect(issue.media.every((item) => !item.trainingEligible)).toBe(true)
        continue
      }
      if (issue.slug === 'tarnished-plant-bug') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(1)
        expect(issue.media[0].hostContext).toBe('organism-only')
        expect(issue.media[0].license).toMatch(/public domain/i)
        expect(issue.media[0].trainingPermission).toBe('permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'japanese-beetle-hemp') {
        expect(issue.media).toHaveLength(2)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(1)
        expect(issue.media.find((item) => item.reviewStatus === 'approved-reference')?.hostContext).toBe('organism-only')
        expect(issue.media.find((item) => item.reviewStatus === 'license-review')?.displayPermission).toBe('unknown')
        expect(issue.media.every((item) => !item.trainingEligible)).toBe(true)
        continue
      }
      if (issue.slug === 'dectes-stem-borer') {
        expect(issue.media).toHaveLength(2)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(1)
        expect(issue.media.find((item) => item.mediaType === 'image')?.hostContext).toBe('organism-only')
        expect(issue.media.find((item) => item.mediaType === 'video')?.hostContext).toBe('non-cannabis')
        expect(issue.media.find((item) => item.mediaType === 'video')?.reviewStatus).toBe('license-review')
        expect(issue.media.every((item) => !item.trainingEligible)).toBe(true)
        continue
      }
      if (issue.slug === 'downy-mildew-pseudoperonospora') {
        expect(issue.media).toHaveLength(2)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media.every((item) => item.hostContext === 'cannabis')).toBe(true)
        expect(issue.media.every((item) => item.reviewStatus === 'license-review')).toBe(true)
        expect(issue.media.every((item) => item.displayPermission === 'unknown')).toBe(true)
        expect(issue.media.every((item) => item.trainingPermission === 'not-permitted')).toBe(true)
        expect(issue.media.every((item) => !item.trainingEligible)).toBe(true)
        continue
      }
      if (issue.slug === 'serratia-marcescens-leaf-spot') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].hostContext).toBe('cannabis')
        expect(issue.media[0].reviewStatus).toBe('license-review')
        expect(issue.media[0].displayPermission).toBe('unknown')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].diagnosticLabel).toContain('not Serratia ground truth')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      const expectedMediaCount = permittedMediaCounts.get(issue.slug)
      if (!expectedMediaCount) {
        expect(issue.media, `${issue.slug} should remain an explicit image gap until rights/provenance are verified`).toEqual([])
        continue
      }

      expect(issue.media.length, `${issue.slug} should have the verified promoted reference count`).toBe(expectedMediaCount)
      for (const media of issue.media) {
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
    }
  })

  it('keeps tarnished plant bug labels organism-linked, source-conflicted, and threshold-free', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'tarnished-plant-bug')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.3)
    expect(confirmation).toContain('upper/middle/lower canopy')
    expect(confirmation).toContain('keep triangular-mark-only, low-resolution, nymph-only, and genus-only observations out of the lygus lineolaris confirmed class')
    expect(confirmation).toContain('retain a source-conflict flag')
    expect(confirmation).toContain('keep symptom-only, insect-only, detached-tissue-only, stock, vendor, generated, unverified, and rights-unclear captures out of automated training')
    expect(warnings).toContain('authoritative hemp sources conflict on foliar injury')
    expect(warnings).toContain('no validated hemp economic or treatment threshold')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Western tarnished plant bug (Lygus hesperus)',
      'Pale legume bug (Lygus elisus)',
      'Big-eyed bug (Geocoris spp., beneficial predator)',
      'False chinch bug or another seed bug',
      'Broad mite',
      'Hemp russet mite',
      'Boron deficiency or another root-zone nutrient disorder',
    ]))
    expect(record?.sources.some((source) => source.doi === '10.1093/jipm/pmz023')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('extension.usu.edu/planthealth/ipm/notes_ag/hemp-lygus-bug'))).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('pnwhandbooks.org/insect/agronomic/hemp/hemp-lygus-bug'))).toBe(true)
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0].hostContext).toBe('organism-only')
    expect(record?.media[0].diagnosticLabel).toContain('laboratory-reared Lygus lineolaris nymph morphology')
    expect(record?.media[0].trainingEligible).toBe(false)
  })

  it('keeps clomazone labels exposure-linked and non-Cannabis media transfer-only', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'herbicide-clomazone-bleaching-injury')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record?.sources.some((source) => source.doi === '10.1094/PHP-03-20-0017-RS')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1002/csc2.20055')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('ucanr.edu/blog/uc-weed-science'))).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('content.ces.ncsu.edu/carotenoid-pigments'))).toBe(true)
    expect(confirmation).toContain('map affected and unaffected cannabis plants')
    expect(confirmation).toContain('susceptible weeds and other plant species')
    expect(confirmation).toContain('laboratory chain of custody')
    expect(confirmation).toContain('keep symptom-only, detached-leaf-only, non-cannabis, generated, vendor, anecdotal, unverified, and exposure-unlinked samples out')
    expect(warnings).toContain('cannot identify clomazone')
    expect(warnings).toContain('one hemp cultivar, one greenhouse soil system, and one pre-emergence rate')
    expect(warnings).toContain('no licensed, plant-linked cannabis clomazone progression image or verified diagnostic video')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Severe iron deficiency',
      'High-light or heat bleaching',
      'Genetic or chimeric variegation',
      'Broad mite or hemp russet mite injury',
      'Contact-herbicide injury',
      'Camera white-balance or exposure artifact',
    ]))
    expect(record?.media).toHaveLength(2)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(2)
    expect(record?.media.every((item) => item.hostContext === 'non-cannabis')).toBe(true)
    expect(record?.media.every((item) => item.trainingPermission === 'not-permitted')).toBe(true)
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
  })

  it('keeps root-binding labels root-ball-linked and non-Cannabis transfer evidence bounded', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'root-binding-container-stress')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const exclusions = record?.exclusions.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record?.sources.some((source) => source.doi === '10.1094/PHP-03-20-0017-RS')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1071/FP12049')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('extension.umd.edu/resource/pot-bound-indoor-plants'))).toBe(true)
    expect(confirmation).toContain('top, bottom, and at least four side quadrants')
    expect(confirmation).toContain('matched same-cultivar, same-age, same-substrate, same-irrigation comparison')
    expect(confirmation).toContain('center and perimeter immediately before and after a documented irrigation event')
    expect(confirmation).toContain('keep canopy-only, detached-root-only, non-cannabis transfer, unmatched, generated, vendor, anecdotal, unverified, and rights-unclear samples out')
    expect(exclusions).toContain('roots visible at drainage holes')
    expect(exclusions).toContain('root-zone ec')
    expect(exclusions).toContain('culture or molecular testing')
    expect(warnings).toContain('non-cannabis transfer evidence')
    expect(warnings).toContain('diagnostic survey rather than a controlled container-size trial')
    expect(warnings).toContain('no licensed, plant-linked cannabis root-binding progression image or verified diagnostic video')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Normal cohesive nursery root ball or vigorous roots at drainage holes',
      'Irrigation channeling or hydrophobic substrate without mechanical root restriction',
      'Pythium root rot',
      'Root-knot nematodes',
      'Container-side heat injury',
    ]))
    expect(record?.media).toEqual([])
  })

  it('keeps drought labels measurement-linked, genotype-bounded, and threshold-safe', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'drought-water-deficit-stress')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const exclusions = record?.exclusions.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.25)
    expect(record?.sources).toHaveLength(5)
    expect(record?.sources.some((source) => source.doi === '10.21273/HORTSCI13510-18')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1080/15427528.2021.1883175')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1016/j.indcrop.2022.115331')).toBe(true)
    expect(confirmation).toContain('multiple center, perimeter, and depth positions')
    expect(confirmation).toContain('same time of day and camera geometry')
    expect(confirmation).toContain('matched same-cultivar irrigated plant')
    expect(confirmation).toContain('air and leaf temperature, relative humidity, vpd, ppfd, and airflow')
    expect(confirmation).toContain('keep symptom-only, detached-leaf-only, single-timepoint, unmatched, sensor-unlinked, generated, vendor, anecdotal, unverified, and rights-unclear captures out')
    expect(exclusions).toContain('root-zone ec')
    expect(exclusions).toContain('overwatering or hypoxia')
    expect(exclusions).toContain('root binding, hydrophobic substrate, preferential flow, blocked emitters')
    expect(warnings).toContain('must not be used as universal thresholds')
    expect(warnings).toContain('does not recommend intentional drought stress')
    expect(warnings).toContain('no licensed, plant-linked cannabis drought progression image or verified diagnostic video')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Normal cultivar-specific or circadian leaf posture',
      'High-temperature or high-VPD midday depression',
      'Salinity / elevated root-zone EC stress',
      'Pythium root rot',
      'Root binding / container-restriction stress',
      'Camera angle, lens perspective, or time-of-day mismatch',
    ]))
    expect(record?.media).toEqual([])
  })

  it('keeps Japanese beetle labels organism-linked, morphology-confirmed, and license-safe', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'japanese-beetle-hemp')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.65)
    expect(confirmation).toMatch(/twelve discrete white abdominal hair patches/)
    expect(confirmation).toMatch(/upper, middle, and lower canopy/)
    expect(confirmation).toMatch(/do not use skeletonization-only frames as species-level ground truth/)
    expect(confirmation).toMatch(/do not infer larval root injury/)
    expect(warnings).toContain('no universal hemp economic threshold')
    expect(warnings).toContain('no explicit reuse license')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining(['Green June beetle or another scarab beetle', 'Cabbage looper', 'Grasshopper feeding', 'Hail or mechanical tearing']))
    expect(record?.sources.some((source) => source.doi === '10.1093/jipm/pmz023')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('extension.unh.edu/resource/hemp-pests'))).toBe(true)
    expect(record?.media).toHaveLength(2)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(1)
    expect(record?.media.find((item) => item.reviewStatus === 'license-review')?.displayPermission).toBe('unknown')
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
  })

  it('keeps Dectes labels organism-linked and non-Cannabis transfer evidence bounded', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'dectes-stem-borer')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.55)
    expect(confirmation).toMatch(/split the stem lengthwise on camera/)
    expect(confirmation).toMatch(/do not identify dectes from a damaged stem alone/)
    expect(confirmation).toMatch(/several symptomatic and asymptomatic stems across several field locations/)
    expect(warnings).toContain('non-cannabis leaf-age, canopy, seasonal, girdling, lodging, yield, and management claims are transfer context only')
    expect(warnings).toContain('no validated hemp action threshold')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining(['Fusarium stem or crown disease', 'Mechanical training split or wind breakage', 'Other stem-boring beetle or moth larva', 'Ashgray blister beetle adult']))
    expect(record?.sources.some((source) => source.doi === '10.1093/jipm/pmag032')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('extension.umd.edu/resource/dectes'))).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('entomology.k-state.edu'))).toBe(true)
    expect(record?.media).toHaveLength(2)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(1)
    expect(record?.media.find((item) => item.mediaType === 'video')?.trainingPermission).toBe('unknown')
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
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
