import { describe, expect, it } from 'vitest'
import { issues } from '../data/issues'
import type { GrowContext, IssueRecord } from '../types'
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

const fixtureIssue = (
  slug: string,
  indicators: string[],
  overrides: Partial<IssueRecord> = {},
): IssueRecord => ({
  id: slug,
  slug,
  name: slug,
  category: 'Environmental stress',
  severity: 'moderate',
  reviewStatus: 'reviewed',
  summary: '',
  affectedParts: [],
  stages: [],
  indicators,
  exclusions: [],
  progression: [],
  lookAlikes: [],
  confirmation: [],
  immediateActions: [],
  correctivePlan: [],
  prevention: [],
  warnings: [],
  sources: [],
  media: [],
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

  it('lets discriminating symptoms outrank a larger pile of generic symptoms', () => {
    const generic = ['General yellowing', 'Stunted growth', 'Leaf spotting']
    const specific = ['Older-leaf interveinal chlorosis', 'Veins remain distinctly green']
    const records = [
      fixtureIssue('generic-candidate', generic),
      fixtureIssue('specific-candidate', specific),
      fixtureIssue('generic-noise-1', generic),
      fixtureIssue('generic-noise-2', generic),
      fixtureIssue('generic-noise-3', generic),
      fixtureIssue('generic-noise-4', generic),
    ]

    const results = rankDifferentials(records, context([...generic, ...specific]), [])
    expect(results[0].issue.slug).toBe('specific-candidate')
    expect(results[0].supporting).toEqual(specific)
  })

  it('downgrades a high-scoring leader when a look-alike is essentially tied', () => {
    const records = [
      fixtureIssue('candidate-a', ['A specific sign 1', 'A specific sign 2', 'A specific sign 3']),
      fixtureIssue('candidate-b', ['B specific sign 1', 'B specific sign 2', 'B specific sign 3']),
    ]

    const results = rankDifferentials(
      records,
      context([
        'A specific sign 1',
        'A specific sign 2',
        'A specific sign 3',
        'B specific sign 1',
        'B specific sign 2',
        'B specific sign 3',
      ]),
      [],
    )

    expect(results[0].confidence).toBe('Moderate')
    expect(results[0].missing).toContain('additional discriminating evidence between the leading look-alikes')
    expect(results[1].confidence).toBe('Moderate')
  })

  it('honors a conservative photo-only confidence cap when a record defines one', () => {
    const record = fixtureIssue(
      'photo-capped',
      ['Distinct sign 1', 'Distinct sign 2', 'Distinct sign 3'],
      { photoOnlyMaxConfidence: 0.5 },
    )

    const results = rankDifferentials(
      [record],
      context(['Distinct sign 1', 'Distinct sign 2', 'Distinct sign 3']),
      [],
    )

    expect(results[0].confidence).toBe('Low')
    expect(results[0].missing).toContain('non-visual confirmation required by issue confidence policy')
  })
})
