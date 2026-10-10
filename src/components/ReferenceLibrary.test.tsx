// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ReferenceLibrary } from './ReferenceLibrary'
import { IssueLibrary } from './IssueLibrary'

afterEach(cleanup)

describe('Reference discovery and guide evidence', () => {
  it('finds the shared copper figure and opens the correct guide', () => {
    const open = vi.fn()
    render(<ReferenceLibrary onOpenIssue={open} />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search reference images' }), { target: { value: 'copper deficiency' } })
    expect(screen.queryByRole('heading', { name: 'Copper deficiency' })).not.toBeNull()
    expect(screen.getByRole('status').textContent).toContain('1 distinct source assets')
    fireEvent.click(screen.getByRole('button', { name: 'Open Copper deficiency guide' }))
    expect(open).toHaveBeenCalledWith('copper-deficiency')
    expect(screen.getByText(/Cannabis plant context · Shared figure/)).not.toBeNull()
  })

  it('combines category and plant-context filters and recovers from no matches', () => {
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    fireEvent.change(screen.getByRole('combobox', { name: 'Condition category' }), { target: { value: 'Nutrient deficiency' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Plant context' }), { target: { value: 'organism-only' } })
    expect(screen.queryByRole('heading', { name: 'No matching reference images' })).not.toBeNull()
    expect(screen.queryByText('No approved photographs yet')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Clear reference filters' }))
    expect(screen.queryByRole('heading', { name: 'No matching reference images' })).toBeNull()
  })

  it('renders affected parts, stages and claim-level sources in a guide', () => {
    render(<IssueLibrary initialSlug="copper-deficiency" onClearInitialSlug={() => {}} />)
    expect(screen.getByRole('heading', { name: 'Where to look' })).not.toBeNull()
    expect(screen.getByText('leaflet bases')).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Growth stages and observation context' })).not.toBeNull()
    expect(screen.getAllByText('Claims supported by this source')).toHaveLength(2)
    expect(screen.getByText(/Published 2026-08-26 · Checked 2026-10-10/)).not.toBeNull()
  })
})
