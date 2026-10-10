// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ReferenceLibrary } from './ReferenceLibrary'
import { IssueLibrary } from './IssueLibrary'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('Reference discovery and guide evidence', () => {
  it('distinguishes reference coverage from diagnostic accuracy', () => {
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    expect(screen.getByRole('heading', { name: 'Visual evidence coverage' })).not.toBeNull()
    expect(screen.getByText(/condition guides currently have at least one approved, displayable visual reference/)).not.toBeNull()
    expect(screen.getByText(/Coverage is not diagnostic accuracy/)).not.toBeNull()
  })

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

  it('filters by documented viewpoint and restores all references when cleared', () => {
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    const viewpoint = screen.getByRole('combobox', { name: 'Image viewpoint' }) as HTMLSelectElement
    const options = [...viewpoint.options].map((option) => option.value).filter((value) => value !== 'All')
    expect(options.length).toBeGreaterThan(0)
    fireEvent.change(viewpoint, { target: { value: options[0] } })
    const shown = screen.getAllByText('View').map((label) => label.nextElementSibling?.textContent)
    expect(shown.length).toBeGreaterThan(0)
    expect(shown.every((value) => value === options[0])).toBe(true)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search reference images' }), { target: { value: 'unlikely-to-exist-reference-xyz' } })
    fireEvent.click(screen.getByRole('button', { name: 'Clear reference filters' }))
    expect((screen.getByRole('combobox', { name: 'Image viewpoint' }) as HTMLSelectElement).value).toBe('All')
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
  it('provides valid section targets and opens a matching look-alike guide', () => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    render(<IssueLibrary initialSlug="copper-deficiency" onClearInitialSlug={() => {}} />)
    const navigation = screen.getByRole('navigation', { name: 'Guide sections' })
    for (const link of navigation.querySelectorAll('a')) {
      expect(document.getElementById(link.hash.slice(1))).not.toBeNull()
    }
    fireEvent.click(screen.getByRole('button', { name: 'Iron deficiency' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Iron deficiency' })).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Back to issue library' }))
    expect(screen.getByRole('textbox', { name: 'Search issue library' })).not.toBeNull()
  })

})
