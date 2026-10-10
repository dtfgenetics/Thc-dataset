import { beforeEach, describe, expect, it } from 'vitest'
import type { InvestigationCase } from '../types'
import { activateInvestigation, createInvestigation, investigationExportFilename, loadActiveInvestigation, loadInvestigations, serializeInvestigationExport, upsertInvestigation } from './investigations'

class MemoryStorage implements Storage {
  private data = new Map<string, string>()
  get length() { return this.data.size }
  clear() { this.data.clear() }
  getItem(key: string) { return this.data.get(key) ?? null }
  key(index: number) { return [...this.data.keys()][index] ?? null }
  removeItem(key: string) { this.data.delete(key) }
  setItem(key: string, value: string) { this.data.set(String(key), String(value)) }
}

Object.defineProperty(globalThis, 'localStorage', {
  value: new MemoryStorage(),
  configurable: true,
})

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

  it('recovers valid cases beside corrupt records without rewriting stored data', () => {
    const valid = makeCase('valid', 'Recovered plant', '2026-09-01T10:00:00.000Z')
    const stored = JSON.stringify([null, { id: 'broken', updatedAt: 42 }, valid])
    localStorage.setItem('thc-grow-doc:investigations:v1', stored)
    expect(loadInvestigations()).toEqual([valid])
    expect(loadActiveInvestigation()).toEqual(valid)
    expect(localStorage.getItem('thc-grow-doc:investigations:v1')).toBe(stored)
  })

  it.each([
    { context: { symptoms: 'not-an-array' } },
    { diagnosisHistory: [null] },
    { evidenceSummary: [{ slot: 'root-crown', quality: 'good', notes: null }] },
    { updatedAt: 'not-a-date' },
    { context: { stage: '', medium: '', ph: '', ec: '', watering: '', recentChanges: '', symptoms: [], importedObservationIds: [42] } },
  ])('rejects malformed nested case data: %j', (corruptFields) => {
    const valid = makeCase('valid', 'Healthy record', '2026-09-01T10:00:00.000Z')
    localStorage.setItem('thc-grow-doc:investigations:v1', JSON.stringify([{ ...valid, id: 'corrupt', ...corruptFields }, valid]))
    expect(loadInvestigations()).toEqual([valid])
    expect(activateInvestigation('corrupt')).toBeUndefined()
  })

  it('does not migrate malformed legacy data into the case registry', () => {
    const stored = JSON.stringify({ id: 'invalid-legacy', context: null })
    localStorage.setItem('thc-grow-doc:investigation:v1', stored)
    const active = loadActiveInvestigation()
    expect(active.id).not.toBe('invalid-legacy')
    expect(active.context.symptoms).toEqual([])
    expect(loadInvestigations()).toEqual([active])
    expect(localStorage.getItem('thc-grow-doc:investigation:v1')).toBe(stored)
  })

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

  it('serializes a portable case export without dropping diagnostic history', () => {
    const investigation = makeCase('case-export', 'Blue Mango F4 #2', '2026-09-28T18:00:00.000Z')
    investigation.context = {
      ...investigation.context,
      temperatureC: '25',
      humidityPercent: '58',
      ppfd: '500',
      dli: '21.6',
      importedObservationIds: ['OBS-temp', 'OBS-rh', 'OBS-ppfd', 'OBS-dli'],
      importedSourceRecordIds: ['growlens:reading-1'],
      importedObservedAt: '2026-09-28T17:55:00.000Z',
    }
    investigation.diagnosisHistory = [{
      reviewedAt: '2026-09-28T18:05:00.000Z',
      leadingIssueSlug: 'magnesium-deficiency',
      leadingIssueName: 'Magnesium deficiency',
      confidence: 'Moderate',
      supporting: ['older leaf interveinal chlorosis'],
      contradicting: [],
      missing: ['root-zone pH'],
      alternativeIssueSlugs: ['potassium-deficiency'],
    }]

    const payload = JSON.parse(serializeInvestigationExport(investigation))
    expect(payload.schemaVersion).toBe(1)
    expect(payload.product).toBe('THC Grow Doc')
    expect(payload.investigation.id).toBe('case-export')
    expect(payload.investigation.diagnosisHistory).toHaveLength(1)
    expect(payload.investigation.context).toMatchObject({
      temperatureC: '25',
      humidityPercent: '58',
      ppfd: '500',
      dli: '21.6',
      importedObservationIds: ['OBS-temp', 'OBS-rh', 'OBS-ppfd', 'OBS-dli'],
      importedSourceRecordIds: ['growlens:reading-1'],
      importedObservedAt: '2026-09-28T17:55:00.000Z',
    })
    expect(investigationExportFilename(investigation)).toBe('thc-grow-doc-blue-mango-f4-2-2026-09-28.json')
  })
})
