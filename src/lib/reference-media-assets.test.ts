import { describe, expect, it } from 'vitest'
import cropManifest from '../../images/reference/crops-manifest.json'
import originalManifest from '../../images/reference/manifest.json'
import { issues } from '../data/catalog'
import { isDisplayableMedia } from './media'
import { localReferenceMediaCoverage, localReferenceMediaUrl, referenceMediaSources } from './reference-media-assets'

type CropRecord = {
  parentId: string
  issueSlug: string
  repositoryPath: string
}

type OriginalRecord = {
  id: string
  sha256: string
}

const crops = cropManifest.records as CropRecord[]
const originals = originalManifest.records as OriginalRecord[]
const originalBySha = new Map(originals.map((record) => [record.sha256, record]))
const originalById = new Map(originals.map((record) => [record.id, record]))

function persistedParentId(media: { id: string; sha256?: string }) {
  if (media.sha256) {
    const bySha = originalBySha.get(media.sha256)
    if (bySha) return bySha.id
  }
  return originalById.get(media.id)?.id
}

describe('persisted reference media', () => {
  const approved = issues.flatMap((issue) => issue.media
    .filter((media) => isDisplayableMedia(media))
    .map((media) => ({ issue, media })))

  it('resolves every scientifically matched persisted parent/diagnosis pair to a reviewed local crop', () => {
    const scientificallyMatched = approved.filter(({ issue, media }) => {
      const parentId = persistedParentId(media)
      return Boolean(parentId && crops.some((crop) => crop.parentId === parentId && crop.issueSlug === issue.slug))
    })
    const resolvedScientificMatches = scientificallyMatched.filter(({ issue, media }) => localReferenceMediaCoverage(media, issue.slug))

    expect(scientificallyMatched.length).toBeGreaterThan(0)
    expect(resolvedScientificMatches).toHaveLength(scientificallyMatched.length)

    for (const { issue, media } of scientificallyMatched) {
      const local = localReferenceMediaUrl(media, issue.slug)
      expect(local).toContain('reference-media/crops/')
      expect(local).not.toContain('/original/')
      expect(local).not.toMatch(/^https?:\/\//)
      expect(referenceMediaSources(media, issue.slug)[0]).toBe(local)
    }
  })

  it('does not substitute a crop from a different persisted source just to increase local coverage', () => {
    for (const { issue, media } of approved) {
      const parentId = persistedParentId(media)
      if (!parentId) continue
      const hasExactCrop = crops.some((crop) => crop.parentId === parentId && crop.issueSlug === issue.slug)
      expect(localReferenceMediaCoverage(media, issue.slug)).toBe(hasExactCrop)
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
