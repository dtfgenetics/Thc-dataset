// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { GrowLog } from './GrowLog'
import { createInvestigation } from '../lib/investigations'

afterEach(() => { cleanup(); localStorage.clear() })

describe('GrowLog investigation ownership', () => {
  it.each(['null', '{}', '[null,42,{}]', '{invalid'])('renders safely with malformed stored history %s', (stored) => {
    localStorage.setItem('thc-grow-doc:log:v2', stored)
    render(<GrowLog investigation={createInvestigation('Plant')} />)
    expect(screen.queryByText('No follow-ups saved for this investigation')).not.toBeNull()
    expect(localStorage.getItem('thc-grow-doc:log:v2')).toBe(stored)
  })

  it('does not expose another case through a shared plant name', () => {
    const investigation = createInvestigation('Active plant')
    localStorage.setItem('thc-grow-doc:log:v2', JSON.stringify([
      { id: 'own', investigationId: investigation.id, plantName: 'Previous name', createdAt: '2026-10-09', note: 'Own follow-up', outcome: 'Monitoring' },
      { id: 'other', investigationId: 'another-case', plantName: 'Active plant', createdAt: '2026-10-09', note: 'Other case follow-up', outcome: 'Monitoring' },
      { id: 'legacy', plantName: 'Active plant', createdAt: '2026-10-09', note: 'Legacy follow-up', outcome: 'Monitoring' },
      { id: 'unrelated', plantName: 'Different plant', createdAt: '2026-10-09', note: 'Unrelated legacy follow-up', outcome: 'Monitoring' },
    ]))
    render(<GrowLog investigation={investigation} />)
    expect(screen.queryByText('Own follow-up')).not.toBeNull()
    expect(screen.queryByText('Legacy follow-up')).not.toBeNull()
    expect(screen.queryByText('Other case follow-up')).toBeNull()
    expect(screen.queryByText('Unrelated legacy follow-up')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Delete log entry for Different plant' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Delete log entry for Previous name' }))
    expect(screen.queryByText('Own follow-up')).toBeNull()
    const stored = JSON.parse(localStorage.getItem('thc-grow-doc:log:v2')!) as { id: string }[]
    expect(stored.map((entry) => entry.id)).toEqual(['other', 'legacy', 'unrelated'])
  })
})
