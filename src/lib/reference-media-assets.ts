import originalManifest from '../../images/reference/manifest.json'
import cropManifest from '../../images/reference/crops-manifest.json'
import type { MediaRecord } from '../types'

type OriginalRecord = {
  id: string
  sha256: string
}

type CropRecord = {
  id: string
  parentId: string
  issueSlug: string
  repositoryPath: string
  severity?: string
}

const originals = originalManifest.records as OriginalRecord[]
const crops = cropManifest.records as CropRecord[]

const originalBySha = new Map(originals.map((record) => [record.sha256, record]))
const originalById = new Map(originals.map((record) => [record.id, record]))

function severityRank(severity?: string) {
  if (severity === 'intermediate') return 0
  if (severity === 'initial') return 1
  if (severity === 'advanced') return 2
  return 3
}

const cropsByIssue = new Map<string, CropRecord[]>()
for (const crop of crops) {
  const existing = cropsByIssue.get(crop.issueSlug) ?? []
  existing.push(crop)
  cropsByIssue.set(crop.issueSlug, existing)
}
for (const records of cropsByIssue.values()) records.sort((a, b) => severityRank(a.severity) - severityRank(b.severity) || a.id.localeCompare(b.id))

function toPublicReferenceUrl(repositoryPath: string) {
  const relative = repositoryPath.replace(/^images\/reference\//, '')
  return `${import.meta.env.BASE_URL}reference-media/${relative}`
}

function findOriginal(media: MediaRecord) {
  if (media.sha256) {
    const bySha = originalBySha.get(media.sha256)
    if (bySha) return bySha
  }
  return originalById.get(media.id)
}

export function localReferenceMediaUrl(media: MediaRecord, issueSlug: string): string | undefined {
  const original = findOriginal(media)
  if (original) {
    const matchedCrop = crops
      .filter((crop) => crop.parentId === original.id && crop.issueSlug === issueSlug)
      .sort((a, b) => severityRank(a.severity) - severityRank(b.severity) || a.id.localeCompare(b.id))[0]
    if (matchedCrop) return toPublicReferenceUrl(matchedCrop.repositoryPath)

    // A persisted parent exists but there is no reviewed crop for this exact
    // parent + diagnosis pair. Do not silently substitute another source's
    // crop under this media record's citation/provenance.
    return undefined
  }

  // Media without a persisted parent may use an issue-level reviewed crop as
  // a display fallback. These records do not claim to be a local derivative
  // of a different persisted source.
  const issueCrop = cropsByIssue.get(issueSlug)?.[0]
  return issueCrop ? toPublicReferenceUrl(issueCrop.repositoryPath) : undefined
}

export function referenceMediaSources(media: MediaRecord, issueSlug: string): Array<string | undefined> {
  return [localReferenceMediaUrl(media, issueSlug), media.thumbnailUrl, media.url]
}

export function localReferenceMediaCoverage(media: MediaRecord, issueSlug: string) {
  return Boolean(localReferenceMediaUrl(media, issueSlug))
}
