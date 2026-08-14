import { describe, expect, it } from 'vitest'
import { issues } from '../data/issues'
import type { GrowContext } from '../types'
import { rankDifferentials } from './diagnostics'

const context = (symptoms: string[], overrides: Partial<GrowContext> = {}): GrowContext => ({
  stage: '',
  medium: '',
  ph: '',
  ec: '',
  watering: '',
  recentChanges: '',
  symptoms,
  ...overrides,
})

describe('rankDifferentials', () => {
  it('returns no fabricated match without symptom evidence', () => {
    expect(rankDifferentials(issues, context([]), [])).toEqual([])
  })

  it('ranks magnesium deficiency without overstating confidence', () => {
    const results = rankDifferentials(issues, context(['Older leaves yellow between green veins', 'Rust or tan spotting']), [])
    expect(results[0].issue.slug).toBe('magnesium-deficiency')
    expect(results[0].confidence).toBe('Moderate')
    expect(results[0].missing).toContain('measured pH')
    expect(results[0].missing).toContain('measured EC/PPM')
  })

  it('keeps viroid differentials low confidence until laboratory confirmation', () => {
    const results = rankDifferentials(issues, context(['Short internodes', 'Brittle stems or leaves', 'Stunted growth']), [])
    expect(results[0].issue.slug).toBe('hop-latent-viroid')
    expect(results[0].missing).toContain('validated laboratory test')
    expect(results[0].missing).not.toContain('measured pH')
    expect(results[0].missing).not.toContain('measured EC/PPM')
    expect(results[0].confidence).toBe('Low')
  })

  it('does not call hemp russet mite high confidence without underside and microscope evidence', () => {
    const results = rankDifferentials(issues, context(['Dull gray or bronzed foliage', 'Brittle or reduced leaf size', 'No webbing despite mite-like damage']), [])
    expect(results[0].issue.slug).toBe('hemp-russet-mite')
    expect(results[0].confidence).toBe('Low')
    expect(results[0].missing).toContain('leaf-underside image')
    expect(results[0].missing).toContain('microscope-confirmed mite identification')
    expect(results[0].missing).not.toContain('measured pH')
    expect(results[0].missing).not.toContain('measured EC/PPM')
  })

  it('keeps root-pathogen confidence low without a root or crown view', () => {
    const results = rankDifferentials(issues, context(['Brown slimy roots', 'Wilting despite moisture', 'Stunting and yellowing']), [])
    expect(results[0].issue.slug).toBe('pythium-root-rot')
    expect(results[0].confidence).toBe('Low')
    expect(results[0].missing).toContain('root or crown view')
  })
})
