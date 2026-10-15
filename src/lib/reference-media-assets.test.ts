import { describe, expect, it } from 'vitest'
import cropManifest from '../../images/reference/crops-manifest.json'
import originalManifest from '../../images/reference/manifest.json'
import gridSpec from '../../data/reference-grid-crop-spec.json'
import { issues } from '../data/catalog'
import { isDisplayableMedia, resolvedDisplayMediaForIssue } from './media'
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
  it('never substitutes adult aphid crops for the separately sourced egg reference', () => {
    const issue = issues.find((item) => item.slug === 'cannabis-aphid')!
    const media = issue.media.find((item) => item.id === 'media-cannabis-aphid-eggs-bugwood-5596882')!
    expect(persistedParentId(media)).toBe(media.id)
    expect(localReferenceMediaUrl(media, issue.slug)).toBeUndefined()
    expect(referenceMediaSources(media, issue.slug).filter(Boolean)).toEqual([media.url])
    expect(originalManifest.records.find((item) => item.id === media.id)?.sha256).toBe(media.sha256)
  })
  it('keeps Figure 4 shared context separate from each panel diagnosis and severity', () => {
    const grid = gridSpec.grids.find((item) => item.id === 'cockson-mn-b-cu-deficiency-figure-4')!
    const panels = cropManifest.records.filter((item) => item.gridId === grid.id)
    expect(panels).toHaveLength(9)
    expect(grid.reason).toContain('left manganese deficiency, center boron deficiency, right copper deficiency')
    expect(grid.reason).toContain('not a single boron-class sample')
    expect(grid.reason).toContain('Copper prose cites Figure 5 inconsistently')
    for (const column of grid.columns) {
      if (!('diagnosis' in column)) throw new Error(`${column.id}: missing diagnosis`)
      const matched = panels.filter((item) => item.issueSlug === column.issueSlug)
      expect(matched).toHaveLength(3)
      expect(matched.map((item) => item.severity).sort()).toEqual(['advanced', 'initial', 'intermediate'])
      for (const panel of matched) {
        expect(panel.reason).toBe(grid.reason)
        if (!panel.columnContext || !('diagnosis' in panel.columnContext)) throw new Error(`${panel.id}: missing diagnosis context`)
        expect(panel.columnContext.diagnosis).toBe(column.diagnosis)
        expect(panel.rowContext?.severity).toBe(panel.severity)
        expect(panel.trainingEligible).toBe(false)
        expect(panel.sourceGroupId).toBe('doi-10.3390-app9204432-fig4')
      }
    }
  })
  it('resolves manganese toxicity to three left-column crops without duplicating or promoting its parent', () => {
    const manganese = issues.find((issue) => issue.slug === 'manganese-toxicity')!
    const references = resolvedDisplayMediaForIssue(manganese, issues)
    expect(manganese.media).toHaveLength(0)
    expect(references).toHaveLength(1)
    const reference = references[0]
    expect(reference.shared).toBe(true)
    expect(reference.ownerSlug).toBe('boron-toxicity')
    expect(reference.media.sourceUrl).toBe('https://doi.org/10.3390/app9204432')
    expect(reference.media.license).toBe('CC BY 4.0')
    expect(reference.media.trainingEligible).toBe(false)
    const parent = persistedParentId(reference.media)
    const matched = cropManifest.records.filter((crop) => crop.issueSlug === manganese.slug)
    expect(matched).toHaveLength(3)
    expect(matched.map((crop) => crop.severity).sort()).toEqual(['advanced', 'initial', 'intermediate'])
    for (const crop of matched) {
      expect(crop.parentId).toBe(parent)
      expect(crop.sourceGroupId).toBe('doi-10.3390-app9204432-fig5')
      expect(crop.box[0]).toBe(188)
      expect(crop.box[2]).toBe(1099)
      expect(crop.trainingEligible).toBe(false)
    }
    expect(issues.flatMap((issue) => issue.media).filter((media) => media.id === reference.media.id)).toHaveLength(1)
    expect(localReferenceMediaUrl(reference.media, manganese.slug)).toContain('crop-manganese-toxicity-reference-intermediate.png')
  })
  it('resolves boron to three center-column crops without duplicating or promoting its parent', () => {
    const boron = issues.find((issue) => issue.slug === 'boron-deficiency')!
    const references = resolvedDisplayMediaForIssue(boron, issues)
    expect(boron.media).toHaveLength(0)
    expect(references).toHaveLength(1)
    const reference = references[0]
    expect(reference.shared).toBe(true)
    expect(reference.ownerSlug).toBe('manganese-deficiency')
    expect(reference.media.sourceUrl).toBe('https://doi.org/10.3390/app9204432')
    expect(reference.media.license).toBe('CC BY 4.0')
    expect(reference.media.trainingEligible).toBe(false)
    const parent = persistedParentId(reference.media)
    const matched = cropManifest.records.filter((crop) => crop.issueSlug === boron.slug)
    expect(matched).toHaveLength(3)
    expect(matched.map((crop) => crop.severity).sort()).toEqual(['advanced', 'initial', 'intermediate'])
    for (const crop of matched) {
      expect(crop.parentId).toBe(parent)
      expect(crop.sourceGroupId).toBe('doi-10.3390-app9204432-fig4')
      expect(crop.box[0]).toBe(970)
      expect(crop.box[2]).toBe(1763)
      expect(crop.trainingEligible).toBe(false)
    }
    expect(issues.flatMap((issue) => issue.media).filter((media) => media.id === reference.media.id)).toHaveLength(1)
    expect(localReferenceMediaUrl(reference.media, boron.slug)).toContain('crop-boron-deficiency-reference-intermediate.png')
  })
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
