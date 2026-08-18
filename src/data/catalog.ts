import { issues as rawCoreIssues } from './issues'
import { supplementalIssues as rawSupplementalIssues } from './supplemental-issues'
import { expandedIssues as rawExpandedIssues } from './expanded-issues'
import { expandedIssuesBatch2 as rawExpandedIssuesBatch2 } from './expanded-issues-batch2'
import { expandedIssuesBatch3 as rawExpandedIssuesBatch3 } from './expanded-issues-batch3'
import { evidenceAugmentationsBySlug } from './evidence-augmentations'
import { categoryOrder } from './categories'
import { verifiedReferenceMediaBySlug } from './verified-reference-media'
import { verifiedReferenceMediaBatch2BySlug } from './verified-reference-media-batch2'
import { verifiedReferenceMediaBatch3BySlug } from './verified-reference-media-batch3'
import type { IssueRecord, SourceRecord } from '../types'

const controlledCoreIssueIds: Record<string, { canonicalId: string; responsePolicyId: string }> = {
  'hop-latent-viroid': { canonicalId: 'CAN-DIS-011', responsePolicyId: 'POL-HLVD' },
  'pythium-root-rot': { canonicalId: 'CAN-ROOT-002', responsePolicyId: 'POL-PYTHIUM' },
  'powdery-mildew': { canonicalId: 'CAN-DIS-001', responsePolicyId: 'POL-PM' },
  'botrytis-gray-mold-bud-rot': { canonicalId: 'CAN-DIS-002', responsePolicyId: 'POL-BOTRYTIS' },
  'two-spotted-spider-mites': { canonicalId: 'CAN-PEST-001', responsePolicyId: 'POL-SPIDER-MITE' },
  'acidic-extreme-substrate-ph-stress': { canonicalId: 'CAN-STRESS-006', responsePolicyId: 'POL-PH-LOCKOUT' },
}

const attachControlledCoreIds = (issue: IssueRecord): IssueRecord => {
  const mapping = controlledCoreIssueIds[issue.slug]
  return mapping ? { ...issue, ...mapping } : issue
}

const normalizeSourceErrata = (source: SourceRecord): SourceRecord => {
  if (source.title === 'Cannabis sativa as a Host of Rice Root Aphid (Hemiptera: Aphididae) in North America') {
    return {
      ...source,
      url: 'https://doi.org/10.1093/jipm/pmaa008',
      doi: '10.1093/jipm/pmaa008',
      publicationDate: '2020-07-20',
    }
  }

  if (source.doi === '10.3390/app9204432') {
    return { ...source, organization: 'Applied Sciences (Cockson et al.)' }
  }

  if (source.title === 'Septoria cannabicola, a new species on Cannabis sativa from Japan') {
    return {
      ...source,
      url: 'https://doi.org/10.47371/mycosci.2023.1.004',
      doi: '10.47371/mycosci.2023.1.004',
      publicationDate: '2024-03-02',
    }
  }

  return source
}

const normalizeKnownErrata = (issue: IssueRecord): IssueRecord => {
  if (issue.slug === 'downy-mildew-pseudoperonospora') {
    return {
      ...issue,
      category: 'Oomycete pathogen',
      summary: 'A foliar oomycete disease of Cannabis. Angular chlorotic-to-brown lesions and dark underside sporulation are stronger clues than top-surface discoloration alone.',
      warnings: issue.warnings.map((warning) => warning.includes('temporary UI grouping')
        ? 'Pseudoperonospora is an oomycete, not a true fungus; disease-management and diagnostic interpretation should preserve that distinction.'
        : warning),
      sources: issue.sources.map(normalizeSourceErrata),
    }
  }

  return {
    ...issue,
    sources: issue.sources.map(normalizeSourceErrata),
  }
}

const applyEvidenceAugmentations = (issue: IssueRecord): IssueRecord => {
  const augmentation = evidenceAugmentationsBySlug[issue.slug]
  if (!augmentation) return issue

  const byKey = new Map<string, SourceRecord>()
  for (const source of [...issue.sources, ...augmentation.sources].map(normalizeSourceErrata)) {
    const key = source.doi || source.url || `${source.title}|${source.organization}`
    const previous = byKey.get(key)
    if (!previous) {
      byKey.set(key, source)
      continue
    }
    byKey.set(key, {
      ...previous,
      ...source,
      authors: [...new Set([...(previous.authors ?? []), ...(source.authors ?? [])])],
      supportedClaims: [...new Set([...previous.supportedClaims, ...source.supportedClaims])],
    })
  }

  return {
    ...issue,
    ...(augmentation.patch ?? {}),
    sources: [...byKey.values()],
    warnings: [...new Set([...issue.warnings, ...(augmentation.appendWarnings ?? [])])],
  }
}

const enrichVerifiedReferenceMedia = (issue: IssueRecord): IssueRecord => {
  const verifiedMedia = [
    ...(verifiedReferenceMediaBySlug[issue.slug] ?? []),
    ...(verifiedReferenceMediaBatch2BySlug[issue.slug] ?? []),
    ...(verifiedReferenceMediaBatch3BySlug[issue.slug] ?? []),
  ]
  if (!verifiedMedia.length) return issue

  const byId = new Map(issue.media.map((item) => [item.id, item]))
  for (const item of verifiedMedia) byId.set(item.id, item)
  return { ...issue, media: [...byId.values()] }
}

export const coreIssues = rawCoreIssues
  .map(attachControlledCoreIds)
  .map(normalizeKnownErrata)
  .map(applyEvidenceAugmentations)
  .map(enrichVerifiedReferenceMedia)

export const supplementalIssues = [...rawSupplementalIssues, ...rawExpandedIssues, ...rawExpandedIssuesBatch2, ...rawExpandedIssuesBatch3]
  .map(normalizeKnownErrata)
  .map(applyEvidenceAugmentations)
  .map(enrichVerifiedReferenceMedia)

export const issues = [...coreIssues, ...supplementalIssues]

export { categoryOrder }

export const symptomOptions = Array.from(new Set(issues.flatMap((item) => item.indicators))).sort()
