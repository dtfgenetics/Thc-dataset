import { describe, expect, it } from 'vitest'
import type { GrowContext, GrowLogEntry, IssueRecord } from '../types'
import { rankDifferentials } from './diagnostics'

const context = (symptoms: string[], overrides: Partial<GrowContext> = {}): GrowContext => ({
  stage: '', medium: '', ph: '', ec: '', watering: '', recentChanges: '', symptoms, ...overrides,
})

const fixtureIssue = (slug: string, indicators: string[], overrides: Partial<IssueRecord> = {}): IssueRecord => ({
  id: slug,
  slug,
  name: slug,
  category: 'Environmental stress',
  severity: 'moderate',
  reviewStatus: 'reviewed',
  summary: '',
  affectedParts: [],
  stages: [],
  indicators,
  exclusions: [],
  progression: [],
  lookAlikes: [],
  confirmation: [],
  immediateActions: [],
  correctivePlan: [],
  prevention: [],
  warnings: [],
  sources: [],
  media: [],
  ...overrides,
})

const historyEntry = (overrides: Partial<GrowLogEntry>): GrowLogEntry => ({
  id: 'history-1',
  createdAt: '2026-09-01T12:00:00.000Z',
  plantName: 'Test plant',
  note: 'Follow-up',
  outcome: 'Monitoring',
  ...overrides,
})

describe('history-aware diagnostic ranking', () => {
  it('uses recurring history only as bounded supporting evidence', () => {
    const record = fixtureIssue('history-candidate', ['Older-leaf interveinal chlorosis', 'Rust spotting'])
    const current = context(['Older-leaf interveinal chlorosis'], { ph: '6.2', ec: '1.4' })
    const history = [historyEntry({
      symptoms: ['Older-leaf interveinal chlorosis'],
      diagnosisIssueSlug: 'history-candidate',
      outcome: 'Stable',
      ph: '5.4',
      ec: '0.7',
    })]

    const [result] = rankDifferentials([record], current, [], history)
    expect(result.historySignals?.length).toBeGreaterThan(0)
    expect(result.confidence).toBe('Low')
  })

  it('treats a resolved prior hypothesis as weakening persistence, not proof against recurrence', () => {
    const record = fixtureIssue('resolved-candidate', ['Distinct sign 1', 'Distinct sign 2'])
    const history = [historyEntry({
      symptoms: ['Distinct sign 1'],
      diagnosisIssueSlug: 'resolved-candidate',
      outcome: 'Resolved',
    })]

    const [result] = rankDifferentials([record], context(['Distinct sign 1', 'Distinct sign 2']), [], history)
    expect(result.historySignals).toContain('this hypothesis was previously marked resolved, which weakens simple persistence as an explanation')
    expect(result.score).toBeGreaterThan(0)
  })
})
