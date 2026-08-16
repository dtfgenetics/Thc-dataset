import { categoryOrder, issues as coreIssues } from './issues'
import { supplementalIssues } from './supplemental-issues'

export const issues = [...coreIssues, ...supplementalIssues]

export { categoryOrder }

export const symptomOptions = Array.from(new Set(issues.flatMap((item) => item.indicators))).sort()
