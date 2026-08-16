import { categoryOrder, issues as coreIssues } from './issues'
import { supplementalIssues as rawSupplementalIssues } from './supplemental-issues'
import type { IssueRecord } from '../types'

// Publisher verification on 2026-08-16 found one DOI typo in the first
// supplemental source batch. Normalize known source errata at the catalog
// boundary so the public app and QA/export layers never publish the stale value.
// The underlying supplemental file can be flattened into this corrected form
// during the next controlled data-file refactor.
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

export const supplementalIssues = rawSupplementalIssues.map(normalizeKnownSourceErrata)
export const issues = [...coreIssues, ...supplementalIssues]

export { categoryOrder }

export const symptomOptions = Array.from(new Set(issues.flatMap((item) => item.indicators))).sort()
