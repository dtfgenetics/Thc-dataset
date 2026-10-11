// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ReferenceLibrary } from './ReferenceLibrary'
import { IssueLibrary } from './IssueLibrary'
import { issues } from '../data/catalog'
import { resolvedDisplayMediaForIssue } from '../lib/media'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('Reference discovery and guide evidence', () => {
  it('explains reference comparison limits and verification', () => {
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    expect(screen.getByRole('heading', { name: 'How to compare a reference image' })).not.toBeNull()
    expect(screen.getByText(/An image comparison is an observation aid, not a laboratory diagnosis/)).not.toBeNull()
    expect(screen.getByText(/Match the view and growth stage/)).not.toBeNull()
  })

  it('distinguishes reference coverage from diagnostic accuracy', () => {
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    expect(screen.getByRole('heading', { name: 'Visual evidence coverage' })).not.toBeNull()
    expect(screen.getByText(/condition guides currently have at least one approved, displayable visual reference/)).not.toBeNull()
    expect(screen.getByText(/Coverage is not diagnostic accuracy/)).not.toBeNull()
  })

  it('exposes accessible visual coverage meter', () => {
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    expect(screen.getByRole('img', { name: /condition guides have displayable visual references/ })).not.toBeNull()
  })

  it('reports actual covered and uncovered guide counts', () => {
    const covered = issues.filter((issue) =>
      resolvedDisplayMediaForIssue(issue, issues).some(({ media }) => Boolean(media.url || media.thumbnailUrl))
    ).length
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    expect(screen.getByText(new RegExp(`^${covered} of ${issues.length} condition guides currently have`))).not.toBeNull()
    expect(screen.getByText(new RegExp(`${issues.length - covered} do not\\.`))).not.toBeNull()
  })

  it('offers navigable guides when visual evidence is missing', () => {
    const open = vi.fn()
    render(<ReferenceLibrary onOpenIssue={open} />)
    const gapSummary = screen.queryByText(/guides without displayable visual references/)
    if (gapSummary) {
      fireEvent.click(gapSummary)
      const first = screen.getAllByRole('button', { name: 'Open guide' })[0]
      expect(first).not.toBeNull()
      fireEvent.click(first)
      expect(open).toHaveBeenCalledOnce()
    } else {
      expect(screen.getByText(/All condition guides currently have at least one displayable visual reference/)).not.toBeNull()
    }
  })

  it('filters uncovered guides without changing the approved reference grid', () => {
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    const search = screen.queryByRole('textbox', { name: 'Search guides missing images' })
    if (search) {
      fireEvent.change(search, { target: { value: 'zzzz-unmatched-condition' } })
      expect(screen.getByText('0 guides match')).not.toBeNull()
      expect(screen.getByText(/No missing-image guides match this search/)).not.toBeNull()
      fireEvent.change(search, { target: { value: '' } })
      expect(screen.queryByText('0 guides match')).toBeNull()
    } else {
      expect(screen.getByText(/All condition guides currently have at least one displayable visual reference/)).not.toBeNull()
    }
  })

  it('filters uncovered guides by category when gaps exist', () => {
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    const filter = screen.queryByRole('combobox', { name: 'Filter missing-image guides by category' })
    if (filter) {
      const options = Array.from((filter as HTMLSelectElement).options)
      if (options.length > 1) {
        fireEvent.change(filter, { target: { value: options[1].value } })
        const expected = Number(options[1].textContent?.match(/\\((\\d+)\\)/)?.[1])
        expect(screen.getByText(`${expected} guides match`)).not.toBeNull()
      }
    } else {
      expect(screen.getByText(/All condition guides currently have at least one displayable visual reference/)).not.toBeNull()
    }
  })

  it('labels category backlog counts as coverage gaps rather than diagnostic priority', () => {
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    if (screen.queryByRole('textbox', { name: 'Search guides missing images' })) {
      expect(screen.getByText(/Largest remaining gaps:/)).not.toBeNull()
      expect(screen.getByText(/not a ranking of diagnostic importance/)).not.toBeNull()
    }
  })

  it('paginates large missing-image inventories and resets pagination after search', () => {
    const missing = issues.filter((issue) => !resolvedDisplayMediaForIssue(issue, issues)
      .some(({ media }) => media.url || media.thumbnailUrl))
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    if (missing.length > 24) {
      expect(screen.getByRole('navigation', { name: 'Missing-image guide pages' })).not.toBeNull()
      expect(screen.getAllByRole('button', { name: 'Open guide' })).toHaveLength(24)
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      expect(screen.getByText(/Page 2 of/)).not.toBeNull()
      fireEvent.change(screen.getByRole('textbox', { name: 'Search guides missing images' }), { target: { value: 'zzzz-unmatched-condition' } })
      expect(screen.getByText('0 guides match')).not.toBeNull()
      expect(screen.queryByRole('navigation', { name: 'Missing-image guide pages' })).toBeNull()
    } else if (missing.length > 0) {
      expect(screen.queryByRole('navigation', { name: 'Missing-image guide pages' })).toBeNull()
    }
  })

  it('shows condition-specific capture guidance for uncovered references', () => {
    const missing = issues.filter((issue) => !resolvedDisplayMediaForIssue(issue, issues)
      .some(({ media }) => media.url || media.thumbnailUrl))
    render(<ReferenceLibrary onOpenIssue={() => {}} />)
    if (missing.length) {
      expect(screen.getAllByText(/Suggested evidence views:/).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/Verification:/).length).toBeGreaterThan(0)
    }
  })

  it('finds the shared copper figure and opens the correct guide', () => {
    const open = vi.fn()
    render(<ReferenceLibrary onOpenIssue={open} />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search reference images' }), { target: { value: 'copper deficiency' } })
    expect(screen.queryByRole('heading', { name: 'Copper deficiency' })).not.toBeNull()
    expect(screen.getByText(/1 distinct source assets/)).not.toBeNull()
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
