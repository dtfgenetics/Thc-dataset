import type { IssueRecord, MediaRecord } from '../types'

// The diagnostic website is a commercial context. Approval to display a
// reference does not override a source license or its use restrictions.
// Keep restricted references in the dataset for attribution and provenance,
// but never render their images through this shared media resolver.
const nonCommercialLicense = /(?:^|[^a-z0-9])cc[\s_-]*by[\s_-]*nc(?:[\s_-]*(?:nd|sa))?(?=$|[^a-z0-9])|non[\s_-]*commercial|creativecommons[.]org\/licenses\/by-nc(?:-nd|-sa)?(?:\/|$)/i
const commercialUseRestriction = /all[\s_-]+rights[\s_-]+reserved|commercial[\s_-]+(?:exploitation|distribution|reproduction)[\s_-]+(?:prohibited|forbidden|not[\s_-]+permitted|not[\s_-]+allowed)|non[\s_-]*commercial|(?:no|not[\s_-]+for)[\s_-]+commercial[\s_-]+(?:use|reuse|display)|commercial[\s_-]+(?:use|reuse|display)[\s_-]+(?:prohibited|forbidden|not[\s_-]+permitted|not[\s_-]+allowed|requires?[\s_-]+(?:written[\s_-]+)?permission)|(?:personal|educational)[\s_-]+use[\s_-]+only/i

export function isDisplayableMedia(media: MediaRecord): boolean {
  // Conflicting rights metadata must fail closed, regardless of which field
  // contains the restriction. Normalize typographic dashes in every field.
  const rightsStatements = [media.license ?? '', ...(media.useLimitations ?? []), media.requiredAttribution ?? '']
  if (rightsStatements.some((statement) => {
    const normalized = statement.replace(/[\u2010-\u2015\u2212]/g, '-')
    return nonCommercialLicense.test(normalized) || commercialUseRestriction.test(normalized)
  })) return false

  // An approved review state is insufficient without an explicit source license.
  // Missing or blank licenses are rights-unclear and must remain quarantined.
  return typeof media.license === 'string'
    && media.license.trim().length > 0
    && media.displayPermission === 'permitted'
    && (media.reviewStatus === 'approved-reference' || media.reviewStatus === 'approved-training')
}

// Some peer-reviewed cannabis figures are licensed composites containing several
// diagnosis classes. The unique asset stays attached to one owning record so its
// ID/hash is never duplicated, while verified related issue pages may display the
// same composite as a shared reference. This is display-only: it does not make the
// full composite training-eligible for the linked diagnosis.
const sharedCompositeHashesByIssue: Record<string, string[]> = {
  'manganese-toxicity': [
    'a5ea13b2d3cbf9e54a74c14cada967951295f773ae78682a6be5537022441ce3',
  ],
  'nitrogen-deficiency': [
    'c9200d6cb4fc0ee7a31908b9df06240a86ec6f2cf53fb8bece5098e4ee422952',
  ],
  'copper-deficiency': [
    'd564930612a16469a967ff1d200a042f62685bb22425ae5bc3e73dda5ef22956',
  ],
  'boron-deficiency': [
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
