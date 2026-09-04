import type { GrowContext, InvestigationCase } from '../types'
import { makeId } from './diagnostics'

const CASES_KEY = 'thc-grow-doc:investigations:v1'
const ACTIVE_CASE_KEY = 'thc-grow-doc:active-investigation:v1'

const emptyContext = (): GrowContext => ({ stage: '', medium: '', ph: '', ec: '', watering: '', recentChanges: '', symptoms: [] })

export function createInvestigation(plantName = 'Active plant'): InvestigationCase {
  const now = new Date().toISOString()
  return { id: makeId('case'), plantName, createdAt: now, updatedAt: now, context: emptyContext(), evidenceSummary: [], diagnosisHistory: [] }
}

export function loadInvestigations(): InvestigationCase[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(CASES_KEY) ?? '[]') as InvestigationCase[]
    return Array.isArray(parsed) ? parsed.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)) : []
  } catch { return [] }
}

export function persistInvestigations(cases: InvestigationCase[]) {
  localStorage.setItem(CASES_KEY, JSON.stringify(cases))
}

export function upsertInvestigation(next: InvestigationCase) {
  const cases = loadInvestigations()
  const updated = [next, ...cases.filter((item) => item.id !== next.id)].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  persistInvestigations(updated)
  localStorage.setItem(ACTIVE_CASE_KEY, next.id)
  return updated
}

export function loadActiveInvestigation(): InvestigationCase {
  const cases = loadInvestigations()
  const activeId = localStorage.getItem(ACTIVE_CASE_KEY)
  const selected = cases.find((item) => item.id === activeId) ?? cases[0]
  if (selected) return selected

  // Migrate the previous single-case storage shape when present.
  try {
    const legacy = localStorage.getItem('thc-grow-doc:investigation:v1')
    if (legacy) {
      const parsed = JSON.parse(legacy) as InvestigationCase
      const migrated = { ...parsed, diagnosisHistory: parsed.diagnosisHistory ?? (parsed.diagnosis ? [parsed.diagnosis] : []) }
      upsertInvestigation(migrated)
      return migrated
    }
  } catch { /* fall through to a fresh case */ }

  const fresh = createInvestigation()
  upsertInvestigation(fresh)
  return fresh
}

export function activateInvestigation(id: string) {
  const match = loadInvestigations().find((item) => item.id === id)
  if (!match) return undefined
  localStorage.setItem(ACTIVE_CASE_KEY, id)
  return match
}
