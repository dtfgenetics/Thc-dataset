import type { GrowLogEntry } from '../types'

export const GROW_LOG_STORAGE_KEY = 'thc-grow-doc:log:v2'

function isLogEntry(value: unknown): value is GrowLogEntry {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const entry = value as Record<string, unknown>
  if (!['id', 'createdAt', 'plantName', 'note', 'outcome'].every((key) => typeof entry[key] === 'string')) return false
  if (!entry.id || !Number.isFinite(Date.parse(entry.createdAt as string))) return false
  const optionalText = ['stage', 'medium', 'ph', 'ec', 'watering', 'recentChanges', 'investigationId', 'diagnosisIssueSlug']
  if (!optionalText.every((key) => entry[key] === undefined || typeof entry[key] === 'string')) return false
  if (entry.symptoms !== undefined && (!Array.isArray(entry.symptoms) || !entry.symptoms.every((symptom) => typeof symptom === 'string'))) return false
  return entry.diagnosisConfidence === undefined || ['Low', 'Moderate', 'High'].includes(entry.diagnosisConfidence as string)
}

export function loadLogEntries(): GrowLogEntry[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(GROW_LOG_STORAGE_KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter(isLogEntry) : []
  } catch {
    return []
  }
}
