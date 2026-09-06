import { beforeEach, describe, expect, it } from 'vitest'
import type { InvestigationCase } from '../types'
import { activateInvestigation, createInvestigation, loadActiveInvestigation, loadInvestigations, upsertInvestigation } from './investigations'

const makeCase = (id: string, plantName: string, updatedAt: string): InvestigationCase => ({
  id,
  plantName,
  createdAt: updatedAt,
  updatedAt,
  context: { stage: '', medium: '', ph: '', ec: '', watering: '', recentChanges: '', symptoms: [] },
  evidenceSummary: [],
  diagnosisHistory: [],
})

describe('investigation registry', () => {
  beforeEach(() => localStorage.clear())

  it('keeps multiple investigations instead of overwriting the active case', () => {
    upsertInvestigation(makeCase('case-a', 'Plant A', '2026-09-01T10:00:00.000Z'))
    upsertInvestigation(makeCase('case-b', 'Plant B', '2026-09-02T10:00:00.000Z'))
    expect(loadInvestigations().map((item) => item.id)).toEqual(['case-b', 'case-a'])
    expect(loadActiveInvestigation().id).toBe('case-b')
  })

  it('reopens an existing investigation without copying it', () => {
    upsertInvestigation(makeCase('case-a', 'Plant A', '2026-09-01T10:00:00.000Z'))
    upsertInvestigation(makeCase('case-b', 'Plant B', '2026-09-02T10:00:00.000Z'))
    expect(activateInvestigation('case-a')?.plantName).toBe('Plant A')
    expect(loadActiveInvestigation().id).toBe('case-a')
    expect(loadInvestigations()).toHaveLength(2)
  })

  it('migrates the previous single-case storage shape and preserves diagnosis history', () => {
    const legacy = makeCase('legacy-case', 'Legacy plant', '2026-09-03T10:00:00.000Z')
    legacy.diagnosis = {
      reviewedAt: '2026-09-03T11:00:00.000Z',
      leadingIssueSlug: 'magnesium-deficiency',
      leadingIssueName: 'Magnesium deficiency',
      confidence: 'Moderate',
      supporting: ['older leaf interveinal chlorosis'],
      contradicting: [],
      missing: ['measured pH'],
      alternativeIssueSlugs: [],
    }
    delete legacy.diagnosisHistory
    localStorage.setItem('thc-grow-doc:investigation:v1', JSON.stringify(legacy))

    const migrated = loadActiveInvestigation()
    expect(migrated.id).toBe('legacy-case')
    expect(migrated.diagnosisHistory).toHaveLength(1)
    expect(loadInvestigations()).toHaveLength(1)
  })

  it('creates a clean investigation with no inherited diagnostic evidence', () => {
    const fresh = createInvestigation('New plant')
    expect(fresh.plantName).toBe('New plant')
    expect(fresh.context.symptoms).toEqual([])
    expect(fresh.evidenceSummary).toEqual([])
    expect(fresh.diagnosisHistory).toEqual([])
  })
})
