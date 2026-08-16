import type { IssueRecord, MediaRecord } from '../types'

export function isDisplayableMedia(media: MediaRecord): boolean {
  return media.displayPermission === 'permitted'
    && (media.reviewStatus === 'approved-reference' || media.reviewStatus === 'approved-training')
}

// Some peer-reviewed cannabis figures are licensed composites containing several
// diagnosis classes. The unique asset stays attached to one owning record so its
// ID/hash is never duplicated, while verified related issue pages may display the
// same composite as a shared reference. This is display-only: it does not make the
// full composite training-eligible for the linked diagnosis.
const sharedCompositeHashesByIssue: Record<string, string[]> = {
  'nitrogen-deficiency': [
    'c9200d6cb4fc0ee7a31908b9df06240a86ec6f2cf53fb8bece5098e4ee422952',
  ],
  'copper-deficiency': [
    'd564930612a16469a967ff1d200a042f62685bb22425ae5bc3e73dda5ef22956',
  ],
}

export interface ResolvedMediaReference {
  media: MediaRecord
  shared: boolean
  ownerSlug: string
}

export function resolvedDisplayMediaForIssue(issue: IssueRecord, records: IssueRecord[]): ResolvedMediaReference[] {
  const direct = issue.media
    .filter(isDisplayableMedia)
    .map((media) => ({ media, shared: false, ownerSlug: issue.slug }))

  const sharedHashes = new Set(sharedCompositeHashesByIssue[issue.slug] ?? [])
  if (!sharedHashes.size) return direct

  const resolved = records.flatMap((owner) => owner.media
    .filter((media) => Boolean(media.sha256) && sharedHashes.has(media.sha256 as string) && isDisplayableMedia(media))
    .map((media) => ({ media, shared: true, ownerSlug: owner.slug })))

  const seen = new Set(direct.map(({ media }) => media.sha256 ?? media.id))
  for (const item of resolved) {
    const key = item.media.sha256 ?? item.media.id
    if (!seen.has(key)) {
      direct.push(item)
      seen.add(key)
    }
  }
  return direct
}

export function hasResolvedDisplayMedia(issue: IssueRecord, records: IssueRecord[]): boolean {
  return resolvedDisplayMediaForIssue(issue, records).length > 0
}
