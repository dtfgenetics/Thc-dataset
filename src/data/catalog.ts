import { issues as rawCoreIssues } from './issues'
import { supplementalIssues as rawSupplementalIssues } from './supplemental-issues'
import { expandedIssues as rawExpandedIssues } from './expanded-issues'
import { categoryOrder } from './categories'
import { verifiedReferenceMediaBySlug } from './verified-reference-media'
import { verifiedReferenceMediaBatch2BySlug } from './verified-reference-media-batch2'
import { verifiedReferenceMediaBatch3BySlug } from './verified-reference-media-batch3'
import type { IssueRecord } from '../types'

// These mappings are not inferred from names. Each pair is directly supported by
// backend/config/diagnostic-response-policy.json, where the policy names exactly
// one canonical diagnosis ID. Ambiguous multi-ID policies remain unmapped here.
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

// Publisher verification on 2026-08-16 found one DOI typo in the first
// supplemental source batch. Normalize known source errata at the catalog
// boundary so the public app and QA/export layers never publish the stale value.
const normalizeKnownSourceErrata = (issue: IssueRecord): IssueRecord => {
  if (issue.slug !== 'rice-root-aphid') return issue

  return {
    ...issue,
    sources: issue.sources.map((source) => source.title === 'Cannabis sativa as a Host of Rice Root Aphid (Hemiptera: Aphididae) in North America'
      ? {
          ...source,
          url: 'https://doi.org/10.1093/jipm/pmaa008',
          doi: '10.1093/jipm/pmaa008',
          publicationDate: '2020-07-20',
        }
      : source),
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
  .map(enrichVerifiedReferenceMedia)

export const supplementalIssues = [...rawSupplementalIssues, ...rawExpandedIssues]
  .map(normalizeKnownSourceErrata)
  .map(enrichVerifiedReferenceMedia)

export const issues = [...coreIssues, ...supplementalIssues]

export { categoryOrder }

export const symptomOptions = Array.from(new Set(issues.flatMap((item) => item.indicators))).sort()
