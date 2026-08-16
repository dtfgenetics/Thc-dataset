import { describe, expect, it } from 'vitest'
import { issues } from '../data/catalog'
import { isDisplayableMedia } from './media'

describe('runtime catalog media quality', () => {
  const allMedia = issues.flatMap((issue) => issue.media.map((media) => ({ issue, media })))
  const approved = allMedia.filter(({ media }) => isDisplayableMedia(media))

  it('keeps media IDs and cryptographic hashes unique across the runtime catalog', () => {
    expect(new Set(allMedia.map(({ media }) => media.id)).size).toBe(allMedia.length)
    expect(new Set(allMedia.map(({ media }) => media.sha256).filter(Boolean)).size)
      .toBe(allMedia.filter(({ media }) => Boolean(media.sha256)).length)
  })

  it('requires every approved runtime image to carry complete provenance metadata', () => {
    for (const { issue, media } of approved) {
      expect(media.url ?? media.thumbnailUrl, `${media.id} has no display URL`).toMatch(/^https:\/\//)
      expect(media.sourceUrl, `${media.id} has no source URL`).toMatch(/^https:\/\//)
      expect(media.creator, `${media.id} has no creator/rights-holder record`).toBeTruthy()
      expect(media.license, `${media.id} has no license`).toBeTruthy()
      expect(media.requiredAttribution, `${media.id} has no required attribution`).toBeTruthy()
      expect(media.diagnosticLabel, `${media.id} has no diagnostic label`).toBeTruthy()
      expect(media.hostSpecies, `${media.id} has no host species`).toBeTruthy()
      expect(media.hostContext, `${media.id} has no host context`).toBeTruthy()
      expect(media.useLimitations.length, `${media.id} has no use limitations`).toBeGreaterThan(0)
      expect(media.sha256, `${media.id} has no sha256`).toMatch(/^[a-f0-9]{64}$/)
      expect(media.perceptualHash, `${media.id} has no perceptual hash`).toMatch(/^[A-Za-z0-9:_-]+$/)
      expect(media.width, `${media.id} missing width`).toBeGreaterThan(0)
      expect(media.height, `${media.id} missing height`).toBeGreaterThan(0)
      expect(media.view, `${media.id} missing view`).toBeTruthy()
      expect(media.confirmation, `${media.id} missing confirmation status`).toBeTruthy()
      expect(media.displayPermission).toBe('permitted')
      expect(['approved-reference', 'approved-training']).toContain(media.reviewStatus)
      expect(issue.sources.length, `${media.id} belongs to an unsourced issue`).toBeGreaterThan(0)
    }
  })

  it('keeps newly promoted composite/experimental references out of training', () => {
    const referenceOnlyIds = new Set([
      'media-rice-root-aphid-cannabis-figure-2',
      'media-fusarium-cannabis-figure-4',
      'media-cannabis-aphid-figure-2',
      'media-powdery-mildew-cannabis-figure-2',
      'media-pythium-hemp-pathogenicity-figure-7',
      'media-hlvd-cannabis-figure-1',
      'media-bctv-cannabis-figure-19',
      'media-two-spotted-spider-mite-hemp-figure-1',
    ])

    for (const { media } of allMedia.filter(({ media }) => referenceOnlyIds.has(media.id))) {
      expect(media.reviewStatus).toBe('approved-reference')
      expect(media.trainingEligible).toBe(false)
      expect(media.useLimitations.join(' ').toLowerCase()).toMatch(/reference|do not|not .*specific|training|laboratory/)
    }
  })
})
