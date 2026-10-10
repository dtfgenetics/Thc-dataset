// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { GROW_LOG_STORAGE_KEY, loadLogEntries } from './grow-log-storage'

afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })
const valid = { id: 'log', createdAt: '2026-10-09', plantName: 'Plant', note: 'Wilt', outcome: 'Monitoring' }

it.each([{ symptoms: [42] }, { ph: 6.2 }, { watering: null }, { createdAt: 'invalid' }, { diagnosisConfidence: 'Confirmed' }, { investigationId: {} }])('retains valid history while excluding malformed fields %j', (fields) => {
  const stored = JSON.stringify([null, { ...valid, ...fields }, valid])
  localStorage.setItem(GROW_LOG_STORAGE_KEY, stored)
  expect(loadLogEntries()).toEqual([valid])
  expect(localStorage.getItem(GROW_LOG_STORAGE_KEY)).toBe(stored)
})

it('returns empty history when browser storage is unavailable', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage unavailable') })
  expect(loadLogEntries()).toEqual([])
})
