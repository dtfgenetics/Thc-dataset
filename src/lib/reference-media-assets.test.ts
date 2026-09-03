import { describe, expect, it } from 'vitest'
import { issues } from '../data/catalog'
import { isDisplayableMedia } from './media'
import { localReferenceMediaCoverage, localReferenceMediaUrl, referenceMediaSources } from './reference-media-assets'

describe('persisted reference media', () => {
  const approved = issues.flatMap((issue) => issue.media
    .filter((media) => isDisplayableMedia(media))
    .map((media) => ({ issue, media })))

  it('prefers same-origin reviewed crops when persisted visual evidence is available', () => {
    const locallyCovered = approved.filter(({ issue, media }) => localReferenceMediaCoverage(media, issue.slug))
    expect(locallyCovered.length).toBeGreaterThanOrEqual(25)

    for (const { issue, media } of locallyCovered) {
      const local = localReferenceMediaUrl(media, issue.slug)
      expect(local).toContain('reference-media/crops/')
      expect(local).not.toContain('/original/')
      expect(local).not.toMatch(/^https?:\/\//)
      expect(referenceMediaSources(media, issue.slug)[0]).toBe(local)
    }
  })

  it('retains licensed remote URLs only as fallback candidates', () => {
    for (const { issue, media } of approved) {
      const sources = referenceMediaSources(media, issue.slug)
      const local = localReferenceMediaUrl(media, issue.slug)
      if (local) expect(sources[0]).toBe(local)
      if (media.thumbnailUrl) expect(sources).toContain(media.thumbnailUrl)
      if (media.url) expect(sources).toContain(media.url)
    }
  })
})
