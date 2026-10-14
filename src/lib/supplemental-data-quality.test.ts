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

  it('keeps fungus gnat injury labels plant-linked, differential-ready, and low-confidence', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'fungus-gnats-root-feeding')
    const indicators = record?.indicators.join(' ').toLowerCase() ?? ''
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.25)
    expect(record?.indicators).toHaveLength(8)
    expect(record?.exclusions).toHaveLength(8)
    expect(record?.progression).toHaveLength(5)
    expect(record?.lookAlikes).toHaveLength(12)
    expect(record?.confirmation).toHaveLength(7)
    expect(record?.sources).toHaveLength(6)
    expect(record?.media).toHaveLength(1)
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Shore flies',
      'Rice root aphid',
      'Pythium or another oomycete root rot',
      'Rhizoctonia sore shin / root rot',
      'Root-zone hypoxia / overwatering',
    ]))
    expect(indicators).toContain('y-shaped wing vein supports fungus gnat over shore fly')
    expect(confirmation).toContain('keep adult counts as a scouting cue, not a causal injury label')
    expect(confirmation).toContain('require plant-linked larvae plus compatible injury for a confirmed injury label')
    expect(confirmation).toContain('route adult-only, sticky-card-only, larva-only, unlinked-root, mixed-organism, low-resolution, non-cannabis, stock, vendor, generated, anecdotal, forum, and unverified samples to human review')
    expect(warnings).toContain('does not supply a universal symptom, severity, threshold, or species diagnosis')
    expect(warnings).toContain('no licensed, plant-linked cannabis injury progression, verified diagnostic video, or species-vouchered cannabis media')
    expect(record?.sources.some((source) => source.doi === '10.3390/insects6020325')).toBe(true)
    expect(record?.sources.some((source) => source.url === 'https://solutions.tennessee.edu/?view_pub_pdf=2571')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('pnwhandbooks.org/insect/hort/greenhouse/greenhouse-ornamentals-fungus-gnat'))).toBe(true)
    expect(record?.sources.some((source) => source.url === 'https://ipm.ucanr.edu/PMG/B/I-DP-BRAD-LV.004.html')).toBe(true)
    expect(record?.sources.some((source) => source.url === 'https://ipm.ucanr.edu/GENERAL/copyright.html')).toBe(true)
    const media = record?.media[0]
    expect(media?.url).toBe('https://ipm.ucanr.edu/PMG/IMAGES/B/I-DP-BRAD-LV.004.jpg')
    expect(media?.sourceUrl).toBe('https://ipm.ucanr.edu/PMG/B/I-DP-BRAD-LV.004.html')
    expect(media?.creator).toBe('Jack Kelly Clark, UC IPM')
    expect(media?.hostContext).toBe('non-cannabis')
    expect(media?.displayPermission).toBe('not-permitted')
    expect(media?.reviewStatus).toBe('license-review')
    expect(media?.trainingPermission).toBe('not-permitted')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.useLimitations.join(' ').toLowerCase()).toContain('media binary is not copied')
    expect(isDisplayableMedia(media!)).toBe(false)
  })

  it('keeps rice root aphid labels plant-linked, root-confirmed, and canopy-cautious', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'rice-root-aphid')
    const indicators = record?.indicators.join(' ').toLowerCase() ?? ''
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.3)
    expect(record?.indicators).toHaveLength(8)
    expect(record?.exclusions).toHaveLength(8)
    expect(record?.progression).toHaveLength(5)
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Cannabis aphid',
      'Fungus gnats',
      'Pythium or another oomycete root rot',
      'Root-knot nematodes',
      'Root-zone hypoxia / overwatering',
    ]))
    expect(indicators).toContain('dead alate aphids caught on upper-leaf hairs or low sticky cards can trigger root-zone inspection')
    expect(confirmation).toContain('preserve intact apterous adults and representative alates')
    expect(confirmation).toContain('finding aphids does not prove they caused every root or canopy symptom')
    expect(confirmation).toContain('keep canopy-only, damage-only, sticky-card-only, alate-only, organism-only, unlinked-root, mixed-arthropod, low-resolution, stock, vendor, generated, anecdotal, forum, and unverified observations out')
    expect(warnings).toContain('increased pathogen susceptibility remains unconfirmed')
    expect(warnings).toContain('evidence gap does not prove outdoor infestation is impossible')
    expect(warnings).toContain('no verified diagnostic video or matched cannabis progression series')
    expect(record?.sources).toHaveLength(3)
    expect(record?.sources.some((source) => source.doi === '10.1093/jipm/pmaa008')).toBe(true)
    expect(record?.sources.some((source) => source.url === 'https://extension.unh.edu/resource/hemp-pests-new-hampshire')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1111/eea.70014')).toBe(true)
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0].sourceUrl).toBe('https://doi.org/10.1093/jipm/pmaa008')
    expect(record?.media[0].license).toBe('CC BY 4.0')
    expect(record?.media[0].hostContext).toBe('cannabis')
    expect(record?.media[0].trainingEligible).toBe(false)
  })

  it('admits only fully verified reference media into supplemental profiles', () => {
    const permittedMediaCounts = new Map([
      ['rice-root-aphid', 1],
      ['fusarium-crown-root-rot', 1],
      ['fusarium-foliar-flower-head-blight', 1],
      ['cannabis-aphid', 1],
      ['root-knot-nematodes', 1],
      ['pseudocercospora-olive-sooty-leaf-spot', 2],
      ['southern-blight-athelia-rolfsii', 1],
      ['heat-light-stress', 1],
      ['drought-water-deficit-stress', 1],
      ['salinity-high-ec-stress', 2],
    ])
    for (const issue of supplementalIssues) {
      if (issue.slug === 'spotted-cucumber-beetle') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].hostContext).toBe('organism-only')
        expect(issue.media[0].license).toBe('CC BY-SA 4.0')
        expect(issue.media[0].reviewStatus).toBe('scientific-review')
        expect(issue.media[0].trainingPermission).toBe('permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'cabbage-looper-hemp') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(1)
        expect(issue.media[0].hostContext).toBe('organism-only')
        expect(issue.media[0].license).toBe('CC BY 3.0 US')
        expect(issue.media[0].trainingPermission).toBe('permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'herbicide-clomazone-bleaching-injury') {
        expect(issue.media).toHaveLength(2)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
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
      if (issue.slug === 'exserohilum-helminthosporium-leaf-blight') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].hostContext).toBe('cannabis')
        expect(issue.media[0].reviewStatus).toBe('license-review')
        expect(issue.media[0].displayPermission).toBe('unknown')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].useLimitations.join(' ')).toContain('no media file is copied')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'sclerotinia-white-mold') {
        expect(issue.media).toHaveLength(3)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media.every((item) => item.hostContext === 'cannabis')).toBe(true)
        expect(issue.media.every((item) => item.reviewStatus === 'license-review')).toBe(true)
        expect(issue.media.every((item) => item.displayPermission === 'unknown')).toBe(true)
        expect(issue.media.every((item) => item.trainingPermission === 'not-permitted')).toBe(true)
        expect(issue.media.every((item) => !item.trainingEligible)).toBe(true)
        expect(issue.media.every((item) => item.useLimitations.join(' ').includes('no image file is stored'))).toBe(true)
        continue
      }
      if (issue.slug === 'bipolaris-leaf-spot') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].license).toBe('CC BY-NC-ND 4.0')
        expect(issue.media[0].displayPermission).toBe('permitted')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'cercospora-leaf-spot') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].license).toBe('CC BY-NC-ND 4.0')
        expect(issue.media[0].displayPermission).toBe('permitted')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'septoria-leaf-spot') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].license).toBe('CC BY-NC-ND 4.0')
        expect(issue.media[0].displayPermission).toBe('permitted')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'curvularia-leaf-spot') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].license).toBe('CC BY-NC-ND 4.0')
        expect(issue.media[0].displayPermission).toBe('permitted')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'hemp-rust') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].license).toBe('CC BY-NC-ND 4.0')
        expect(issue.media[0].displayPermission).toBe('permitted')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'armyworm-caterpillar-feeding') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].license).toContain('All rights reserved')
        expect(issue.media[0].displayPermission).toBe('not-permitted')
        expect(issue.media[0].reviewStatus).toBe('license-review')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'fungus-gnats-root-feeding') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].license).toContain('software and electronic-media distribution require written consent')
        expect(issue.media[0].displayPermission).toBe('not-permitted')
        expect(issue.media[0].reviewStatus).toBe('license-review')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'root-binding-container-stress') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].hostContext).toBe('non-cannabis')
        expect(issue.media[0].license).toContain('no item-level reuse license stated')
        expect(issue.media[0].displayPermission).toBe('not-permitted')
        expect(issue.media[0].reviewStatus).toBe('license-review')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        continue
      }
      if (issue.slug === 'rhizoctonia-sore-shin-root-rot') {
        expect(issue.media).toHaveLength(1)
        expect(issue.media.filter(isDisplayableMedia)).toHaveLength(0)
        expect(issue.media[0].hostContext).toBe('cannabis')
        expect(issue.media[0].license).toContain('no item-level reuse license stated')
        expect(issue.media[0].displayPermission).toBe('unknown')
        expect(issue.media[0].reviewStatus).toBe('license-review')
        expect(issue.media[0].trainingPermission).toBe('not-permitted')
        expect(issue.media[0].trainingEligible).toBe(false)
        expect(issue.media[0].sha256).toMatch(/^[a-f0-9]{64}$/)
        expect(issue.media[0].perceptualHash).toMatch(/^dhash64:[a-f0-9]{16}$/)
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

  it('keeps the UF/IFAS hemp rust composite intact, reference-only, and non-training', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'hemp-rust')
    const media = record?.media[0]
    expect(record?.sources).toHaveLength(1)
    expect(record?.sources[0].doi).toBe('10.32473/edis-pp379-2024')
    expect(record?.warnings.join(' ').toLowerCase()).toContain('alternate host is unknown')
    expect(media?.creator).toContain('Zachariah Hansen')
    expect(media?.license).toBe('CC BY-NC-ND 4.0')
    expect(media?.sourceUrl).toBe('https://ask.ifas.ufl.edu/publication/PP379')
    expect(media?.sha256).toBe('e41cdcc830b272b2a05bc22791e5375853f48fa4561021db21487667a96d3f25')
    expect(media?.perceptualHash).toBe('dhash64:d4d4d4d4fc2b8407')
    expect(media?.width).toBe(634)
    expect(media?.height).toBe(600)
    expect(media?.trainingPermission).toBe('not-permitted')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.useLimitations.join(' ').toLowerCase()).toContain('panel extraction')
  })

  it('keeps spotted cucumber beetle labels adult-linked, root-conflicted, and media-safe', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'spotted-cucumber-beetle')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.35)
    expect(record?.sources).toHaveLength(5)
    expect(record?.sources.some((source) => source.doi === '10.1093/jipm/pmz023')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1093/jipm/pmad016')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('pnwhandbooks.org/insect/agronomic/hemp/hemp-cucumber-beetle'))).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('extension.usu.edu/planthealth/ipm/notes_ag/hemp-spotted-cucumber-beetle'))).toBe(true)
    expect(confirmation).toContain('do not assign species or subspecies from yellow-green color or spot count alone')
    expect(confirmation).toContain('require active feeding or temporally linked new injury on the same hemp plant')
    expect(confirmation).toContain('utah guidance says larvae are not known to feed on hemp roots while missouri extension states they can')
    expect(confirmation).toContain('do not transfer bacterial-wilt vector status, root-feeding injury, thresholds, severity, or yield effects')
    expect(confirmation).toContain('keep damage-only, organism-only, trap-only, root-only, larva-only, incomplete-morphology, low-resolution, generated, vendor, anecdotal, forum, and unverified samples out')
    expect(warnings).toContain('hemp sources conflict on root feeding')
    expect(warnings).toContain('no licensed, plant-linked hemp feeding progression or verified diagnostic video')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining(['Japanese beetle', 'Striped cucumber beetle', 'Western corn rootworm adult', 'Northern corn rootworm adult', 'Armyworm or fall armyworm', 'Hail, wind, handling, equipment, or training tear']))
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0].sourceUrl).toBe('https://commons.wikimedia.org/wiki/File:Spotted_cucumber_beetle_(72669).jpg')
    expect(record?.media[0].sha256).toBe('f8d038c6885ef1d26b7170ab16f1705a41bda7156051547db63918209d949f6b')
    expect(record?.media[0].perceptualHash).toBe('dhash64:3333c86868e0695c')
    expect(record?.media[0].confirmation).toBe('visual')
    expect(record?.media[0].reviewStatus).toBe('scientific-review')
    expect(record?.media[0].trainingEligible).toBe(false)
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
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(0)
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
    expect(warnings).toContain('one institutional non-cannabis pot-bound root-mass photograph is indexed')
    expect(warnings).toContain('no licensed, plant-linked cannabis root-binding progression image or verified diagnostic video')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Normal cohesive nursery root ball or vigorous roots at drainage holes',
      'Irrigation channeling or hydrophobic substrate without mechanical root restriction',
      'Pythium root rot',
      'Root-knot nematodes',
      'Container-side heat injury',
    ]))
    expect(record?.media).toHaveLength(1)
    const media = record?.media[0]
    expect(media?.id).toBe('media-pot-bound-root-mass-umd-reference-only')
    expect(media?.url).toContain('extension.umd.edu/sites/extension.umd.edu/files/styles/optimized/public/2021-03/')
    expect(media?.sourceUrl).toBe('https://extension.umd.edu/resource/pot-bound-indoor-plants')
    expect(media?.hostContext).toBe('non-cannabis')
    expect(media?.displayPermission).toBe('not-permitted')
    expect(media?.trainingPermission).toBe('not-permitted')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.width).toBe(1920)
    expect(media?.height).toBe(1080)
    expect(record?.media.filter(isDisplayableMedia)).toHaveLength(0)
  })

  it('keeps drought labels measurement-linked, genotype-bounded, and threshold-safe', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'drought-water-deficit-stress')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const exclusions = record?.exclusions.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.25)
    expect(record?.sources).toHaveLength(6)
    expect(record?.sources.some((source) => source.doi === '10.21273/HORTSCI13510-18')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1080/15427528.2021.1883175')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.1016/j.indcrop.2022.115331')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.3389/fpls.2026.1930650')).toBe(true)
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
    expect(warnings).toContain('final-harvest, six-panel study composite rather than a longitudinal diagnostic sequence')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Normal cultivar-specific or circadian leaf posture',
      'High-temperature or high-VPD midday depression',
      'Salinity / elevated root-zone EC stress',
      'Pythium root rot',
      'Root binding / container-restriction stress',
      'Camera angle, lens perspective, or time-of-day mismatch',
    ]))
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0]).toMatchObject({
      id: 'frontiers-cannabis-drought-figure-4-2026',
      sourceUrl: 'https://doi.org/10.3389/fpls.2026.1930650',
      license: 'CC BY 4.0',
      displayPermission: 'permitted',
      reviewStatus: 'approved-reference',
      trainingPermission: 'permitted',
      sha256: '52fdde639715c262b3774d26a833ad5bf372867a220e505be8ec57fcd4f55f2b',
      perceptualHash: 'dhash64:cc4949596c6d4d4d',
      width: 1003,
      height: 1176,
      trainingEligible: false,
    })
    expect(record?.media[0].useLimitations.join(' ')).toContain('do not detach panels')
  })

  it('keeps salinity labels chemistry-linked, composition-aware, and threshold-safe', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'salinity-high-ec-stress')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const exclusions = record?.exclusions.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record?.sources).toHaveLength(3)
    expect(record?.sources.some((source) => source.doi === '10.3389/fpls.2024.1293184')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.3389/fpls.2020.01169')).toBe(true)
    expect(record?.sources.some((source) => source.doi === '10.17660/ActaHortic.2023.1377.97')).toBe(true)
    expect(confirmation).toContain('temperature compensation, units, date, and plant or irrigation-zone identity')
    expect(confirmation).toContain('matched same-cultivar unaffected control')
    expect(confirmation).toContain('do not infer ion composition from ec')
    expect(confirmation).toContain('before exposure, during the ec rise, before correction, and during recovery')
    expect(confirmation).toContain('keep symptom-only, detached-leaf-only, single-timepoint, unmatched, meter-unlinked, composition-unknown, generated, vendor, anecdotal, forum, unverified, and rights-unclear captures out')
    expect(exclusions).toContain('overwatering and hypoxia')
    expect(exclusions).toContain('root-zone ph')
    expect(exclusions).toContain('root-ball geometry, substrate compaction, container temperature, and root restriction')
    expect(warnings).toContain('ec is a conductivity measurement, not an ion identity')
    expect(warnings).toContain('not universal safe, toxic, correction, or training-label thresholds')
    expect(warnings).toContain('two cc by treatment-response diagrams are indexed as reference context')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Drought / water-deficit stress',
      'Root-zone hypoxia / overwatering',
      'Potassium deficiency',
      'Nitrogen toxicity or excessive ammonium',
      'Pythium or Fusarium root/crown disease',
      'Normal late-flowering senescence',
    ]))
    expect(record?.media).toHaveLength(2)
    expect(record?.media.map((item) => item.id)).toEqual([
      'media-salinity-cannabis-growth-index-yep-figure-1',
      'media-salinity-cannabis-chlorophyll-index-yep-figure-2',
    ])
    expect(record?.media.every((item) => item.view === 'diagram')).toBe(true)
    expect(record?.media.every((item) => item.license?.includes('CC BY 4.0') === true)).toBe(true)
    expect(record?.media.every((item) => item.displayPermission === 'permitted')).toBe(true)
    expect(record?.media.every((item) => item.trainingPermission === 'permitted')).toBe(true)
    expect(record?.media.every((item) => item.trainingEligible === false)).toBe(true)
    expect(record?.media.map((item) => item.sha256)).toEqual([
      '3d4e37d7281dc574ca2ebb5db36e35bfa2466f1bddbd265c787db932d1423548',
      'f433c9b480ce5592ea9a292e21160a9a3cfecb34282dfbecef3db3e524e71f1f',
    ])
    expect(record?.media.map((item) => item.perceptualHash)).toEqual([
      'dhash64:3358103121a2e66a',
      'dhash64:3316424266b2d146',
    ])
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

  it('keeps cabbage looper labels larva-linked and laboratory evidence bounded', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'cabbage-looper-hemp')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const exclusions = record?.exclusions.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.35)
    expect(record?.sources).toHaveLength(4)
    expect(record?.sources.some((source) => source.doi === '10.1093/hr/uhad207')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('pubs.ext.vt.edu/3104/3104-1544'))).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('ask.ifas.ufl.edu/publication/IN273'))).toBe(true)
    expect(confirmation).toContain('two abdominal proleg pairs on segments five and six')
    expect(confirmation).toContain('same uninterrupted sequence')
    expect(confirmation).toContain('did not observe trichoplusia ni in its field plots')
    expect(confirmation).toContain('keep damage-only, frass-only, egg-only, adult-only, cocoon-only, non-cannabis, detached-leaf-only, generated, vendor, anecdotal, unverified, low-resolution, and organism/injury-unlinked samples out')
    expect(exclusions).toContain('dark thoracic legs or microscopic body microspines support soybean looper')
    expect(warnings).toContain('model generalist in detached-leaf assays')
    expect(warnings).toContain('no validated hemp economic or treatment threshold')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Soybean looper or another plusiine looper',
      'Imported cabbageworm',
      'Armyworm or fall armyworm',
      'Japanese beetle',
      'Slug or snail feeding',
      'Hail, wind, handling, or training tear',
    ]))
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0].hostContext).toBe('organism-only')
    expect(record?.media[0].sourceUrl).toBe('https://commons.wikimedia.org/wiki/File:Trichoplusia_ni_larva.jpg')
    expect(record?.media[0].sha256).toBe('8141b5267664d9d156422db069129bc5d71362a04833dd41c882cc0bc5bd78dd')
    expect(record?.media[0].trainingEligible).toBe(false)
  })

  it('keeps armyworm complex labels larva-linked, multi-species, and threshold-free', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'armyworm-caterpillar-feeding')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const exclusions = record?.exclusions.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.3)
    expect(record?.indicators).toHaveLength(8)
    expect(record?.exclusions).toHaveLength(8)
    expect(record?.progression).toHaveLength(5)
    expect(record?.lookAlikes).toHaveLength(12)
    expect(record?.confirmation).toHaveLength(7)
    expect(record?.sources).toHaveLength(5)
    expect(record?.media).toHaveLength(1)
    expect(record?.lookAlikes).toEqual(expect.arrayContaining([
      'Corn earworm',
      'Tobacco budworm',
      'Cabbage looper',
      'Spotted or variegated cutworm',
      'Japanese beetle',
      'Hail, wind, handling, equipment, or training tear',
    ]))
    expect(confirmation).toContain('count the three true thoracic leg pairs and rear proleg pairs')
    expect(confirmation).toContain('do not assign armyworm from silk, frass, tunneling, or bud rot without excluding corn earworm and tobacco budworm')
    expect(confirmation).toContain('keep damage-only, frass-only, silk-only, egg-only, moth-only, body-color-only, incomplete-marking, detached-leaf, non-cannabis, organism/injury-unlinked, low-resolution, stock, shutterstock, bugguide, vendor, generated, anecdotal, forum, and unverified samples out')
    expect(exclusions).toContain('three rear proleg pairs and a looping gait supports cabbage, alfalfa, or soybean looper')
    expect(warnings).toContain('neither regional observation establishes universal prevalence, severity, yield loss, or an economic threshold')
    expect(warnings).toContain('only link metadata and verified technical fingerprints are indexed; no media binary is copied, display and automated training are prohibited, and no training-eligible asset is included')
    expect(record?.sources.some((source) => source.doi === '10.1093/jipm/pmad028')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('extension.usu.edu/planthealth/ipm/notes_ag/hemp-armyworms'))).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('pnwhandbooks.org/insect/agronomic/hemp/hemp-caterpillars'))).toBe(true)
    expect(record?.sources.some((source) => source.url === 'https://www.usu.edu/copyright/index.cfm')).toBe(true)
    const media = record?.media[0]
    expect(media?.url).toBe('https://extension.usu.edu/planthealth/ipm/images/agricultural/hemp/armyworm/IMG_1705.jpg')
    expect(media?.sourceUrl).toBe('https://extension.usu.edu/planthealth/ipm/notes_ag/hemp-armyworms')
    expect(media?.creator).toBe('Utah State University Extension Integrated Pest Management Program')
    expect(media?.license).toContain('All rights reserved')
    expect(media?.hostContext).toBe('cannabis')
    expect(media?.displayPermission).toBe('not-permitted')
    expect(media?.reviewStatus).toBe('license-review')
    expect(media?.trainingPermission).toBe('not-permitted')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.sha256).toBe('ef606bfd902e3501c8d7539348fedd38382859f5de5a000870fb53d0b8d7032b')
    expect(media?.perceptualHash).toBe('dhash64:7870c884e3cc9c1a')
    expect(media?.width).toBe(810)
    expect(media?.height).toBe(660)
    expect(media?.useLimitations.join(' ').toLowerCase()).toContain('source caption supports only that the larva was found on hemp')
  })

  it('keeps anthracnose labels lesion-linked, multilocus-confirmed, and media-safe', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'anthracnose-colletotrichum-leaf-spot')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const exclusions = record?.exclusions.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.3)
    expect(record?.sources).toHaveLength(2)
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-10-19-2216-PDN')).toBe(true)
    expect(record?.sources.some((source) => source.url.includes('Science-of-Hemp-Conference-Proceedings'))).toBe(true)
    expect(confirmation).toContain('same intact early lesions through center cracking or loss')
    expect(confirmation).toContain('plant-linked multilocus sequence evidence')
    expect(confirmation).toContain('symptom reproduction, reisolation, and symptomless controls')
    expect(confirmation).toContain('keep symptom-only, shot-hole-only, detached-leaf-only, mixed-pathogen, culture-unlinked, single-locus-only, generated, vendor, anecdotal, forum, unverified, and low-resolution samples out')
    expect(exclusions).toContain('physical holes, chewing, hail tears, handling damage, or training injury')
    expect(warnings).toContain('does not establish national prevalence, cultivar susceptibility, universal canopy or leaf-age preference, infection timing, yield loss, or action thresholds')
    expect(warnings).toContain('no image or video was indexed')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining(['Cercospora leaf spot', 'Septoria leaf spot complex', 'Alternaria leaf spot', 'Bacterial leaf spot', 'Caterpillar, beetle, slug, or snail feeding', 'Hail, wind, handling, or training tear']))
    expect(record?.media).toEqual([])
  })

  it('keeps the UF/IFAS Bipolaris figure reference-only and non-training', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'bipolaris-leaf-spot')
    const media = record?.media[0]
    expect(record?.sources.some((source) => source.doi === '10.32473/edis-pp379-2024')).toBe(true)
    expect(record?.media).toHaveLength(1)
    expect(media?.creator).toBe('Thomas Isakeit, Texas A&M University')
    expect(media?.license).toBe('CC BY-NC-ND 4.0')
    expect(media?.sourceUrl).toBe('https://ask.ifas.ufl.edu/publication/PP379')
    expect(media?.sha256).toBe('0ae5416c4053f7782e5ca3e09e31aca2e5a51c3476f22eb3983aef9395a61d09')
    expect(media?.perceptualHash).toBe('dhash64:4547038b9b264209')
    expect(media?.trainingPermission).toBe('not-permitted')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.useLimitations.join(' ').toLowerCase()).toContain('no image file is stored')
  })

  it('keeps the UF/IFAS Cercospora composite intact, reference-only, and non-training', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'cercospora-leaf-spot')
    const media = record?.media[0]
    expect(record?.sources).toHaveLength(5)
    expect(record?.sources.some((source) => source.doi === '10.32473/edis-pp379-2024')).toBe(true)
    expect(record?.warnings.join(' ').toLowerCase()).toContain('institutional differential, not a lesion-linked laboratory record')
    expect(record?.media).toHaveLength(1)
    expect(media?.creator).toBe('Marcus Marin, Jacqueline Coburn, Johan Desaeger, and Natalia Peres; UF/IFAS GCREC')
    expect(media?.license).toBe('CC BY-NC-ND 4.0')
    expect(media?.sourceUrl).toBe('https://ask.ifas.ufl.edu/publication/PP379')
    expect(media?.sha256).toBe('cd7f347351c0f4199d803b8f4333ef37cb177035956e0b99c2b29c7f0d6008c7')
    expect(media?.perceptualHash).toBe('dhash64:860f2bc8f6e787f3')
    expect(media?.view).toBe('whole-plant')
    expect(media?.trainingPermission).toBe('not-permitted')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.useLimitations.join(' ').toLowerCase()).toContain('do not separate panels')
  })

  it('keeps the UF/IFAS Septoria image upper-surface-only, reference-only, and non-training', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'septoria-leaf-spot')
    const media = record?.media[0]
    expect(record?.sources).toHaveLength(6)
    expect(record?.sources.some((source) => source.doi === '10.32473/edis-pp379-2024')).toBe(true)
    expect(record?.warnings.join(' ').toLowerCase()).toContain('institutional upper-surface differential, not a lesion-linked laboratory record')
    expect(record?.media).toHaveLength(1)
    expect(media?.creator).toBe('Nicole Gauthier, University of Kentucky')
    expect(media?.license).toBe('CC BY-NC-ND 4.0')
    expect(media?.sourceUrl).toBe('https://ask.ifas.ufl.edu/publication/PP379')
    expect(media?.sha256).toBe('5d5771e1a14167124aeb196c3db016236fe00c9383d75891812dd76f95309192')
    expect(media?.perceptualHash).toBe('dhash64:2d87931b2d73e7ce')
    expect(media?.view).toBe('close-up')
    expect(media?.trainingPermission).toBe('not-permitted')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.useLimitations.join(' ').toLowerCase()).toContain('upper leaf surface')
  })

  it('keeps the UF/IFAS Curvularia image whole-leaf-only, reference-only, and non-training', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'curvularia-leaf-spot')
    const media = record?.media[0]
    expect(record?.sources).toHaveLength(2)
    expect(record?.sources.some((source) => source.doi === '10.1094/PDIS-03-20-0546-PDN')).toBe(true)
    expect(record?.warnings.join(' ').toLowerCase()).toContain('institutional whole-leaf differential')
    expect(media?.creator).toContain('Marcus Marin')
    expect(media?.license).toBe('CC BY-NC-ND 4.0')
    expect(media?.sourceUrl).toBe('https://ask.ifas.ufl.edu/publication/PP379')
    expect(media?.sha256).toBe('66762b5fcd00a6fe5cf62b569efb0dfe59c86e167964a289483b87cc969af832')
    expect(media?.perceptualHash).toBe('dhash64:5193d25474b070c9')
    expect(media?.view).toBe('close-up')
    expect(media?.trainingPermission).toBe('not-permitted')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.useLimitations.join(' ').toLowerCase()).toContain('paired underside')
  })

  it('keeps Bipolaris labels lesion-linked, multilocus-bounded, and media-safe', () => {
    const record = supplementalIssues.find((issue) => issue.slug === 'bipolaris-leaf-spot')
    const confirmation = record?.confirmation.join(' ').toLowerCase() ?? ''
    const warnings = record?.warnings.join(' ').toLowerCase() ?? ''

    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.3)
    expect(record?.sources).toHaveLength(4)
    expect(record?.sources.map((source) => source.doi)).toEqual(expect.arrayContaining([
      '10.1094/PHP-01-20-0004-BR',
      '10.1094/PDIS-11-23-2483-RE',
      '10.1080/00275514.2023.2224699',
      '10.32473/edis-pp379-2024',
    ]))
    expect(confirmation).toContain('use lesion-linked fungal morphology and validated molecular evidence')
    expect(confirmation).toContain('require validated multilocus evidence')
    expect(confirmation).toContain('symptom reproduction, recovery of the same organism, and symptomless appropriate controls')
    expect(confirmation).toContain('keep symptom-only, detached-leaf-only, mixed-pathogen, culture-unlinked, its-only, single-locus-only, low-resolution, generated, vendor, anecdotal, forum, and unverified samples out')
    expect(warnings).toContain('study-specific observations, not universal bipolaris timing, distribution, susceptibility, yield, or action thresholds')
    expect(warnings).toContain('institutional differential, not a lesion-linked laboratory record')
    expect(record?.lookAlikes).toEqual(expect.arrayContaining(['Septoria leaf spot complex', 'Cercospora leaf spot', 'Pseudocercospora olive leaf spot', 'Alternaria leaf spot', 'Anthracnose leaf spot', 'Bacterial leaf spot', 'Caterpillar, beetle, slug, or snail feeding', 'Hail, wind, handling, or training tear']))
    expect(record?.media).toHaveLength(1)
  })

  it('keeps promoted supplemental media hashes unique', () => {
    const media = supplementalIssues.flatMap((issue) => issue.media)
    const sha256 = media.flatMap((item) => item.sha256 ? [item.sha256] : [])
    const perceptualHashes = media.flatMap((item) => item.perceptualHash ? [item.perceptualHash] : [])
    expect(new Set(media.map((item) => item.id)).size).toBe(media.length)
    expect(new Set(sha256).size).toBe(sha256.length)
    expect(new Set(perceptualHashes).size).toBe(perceptualHashes.length)
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

    expect(cannabisAphid?.photoOnlyMaxConfidence).toBe(0.35)
    expect(cannabisAphid?.indicators).toHaveLength(8)
    expect(cannabisAphid?.exclusions).toHaveLength(10)
    expect(cannabisAphid?.progression).toHaveLength(5)
    expect(cannabisAphid?.lookAlikes).toHaveLength(14)
    expect(cannabisAphid?.confirmation).toHaveLength(7)
    expect(cannabisAphid?.affectedParts.join(' ').toLowerCase()).toMatch(/leaf|stem|petiole/)
    expect(cannabisAphid?.exclusions.join(' ').toLowerCase()).toMatch(/only roots or growing medium contain/)
    expect(cannabisAphid?.confirmation.join(' ').toLowerCase()).toMatch(/exclude phorodon humuli/)
    expect(cannabisAphid?.confirmation.join(' ').toLowerCase()).toMatch(/validated molecular identification/)
    expect(cannabisAphid?.warnings.join(' ').toLowerCase()).toMatch(/human review is mandatory/)
    expect(cannabisAphid?.warnings.join(' ').toLowerCase()).toMatch(/not universal susceptibility, injury, economic, or treatment thresholds/)
    expect(cannabisAphid?.sources.map((item) => item.doi)).toEqual(expect.arrayContaining(['10.5281/zenodo.3710022', '10.3389/fpls.2023.1223894', '10.3390/plants14060931']))
    expect(cannabisAphid?.media).toHaveLength(1)
    expect(cannabisAphid?.media[0]?.trainingEligible).toBe(false)
    expect(cannabisAphid?.media[0]?.useLimitations.join(' ').toLowerCase()).toMatch(/mixed-scale, multi-panel|panel-resolved/)
    expect(rootAphid?.affectedParts.join(' ').toLowerCase()).toMatch(/root/)
    expect(rootAphid?.confirmation.join(' ').toLowerCase()).toMatch(/roots|root zone/)
    expect(rootAphid?.sources.map((item) => item.doi)).toContain('10.1111/eea.70014')
    expect(rootAphid?.warnings.join(' ').toLowerCase()).toMatch(/multiplied more strongly on rye and barley than on cannabis/)
    expect(rootAphid?.warnings.join(' ').toLowerCase()).toMatch(/trap crop.*requires commercial-production testing/)
  })
})
