import { describe, expect, it } from 'vitest'
import { issues } from '../data/issues'
import type { GrowContext } from '../types'
import { rankDifferentials } from './diagnostics'

const context = (symptoms: string[]): GrowContext => ({ stage: '', medium: '', ph: '', ec: '', watering: '', recentChanges: '', symptoms })

describe('rankDifferentials', () => {
  it('returns no fabricated match without symptom evidence', () => {
    expect(rankDifferentials(issues, context([]), [])).toEqual([])
  })

  it('ranks magnesium deficiency for its characteristic pattern', () => {
    const results = rankDifferentials(issues, context(['Older leaves yellow between green veins', 'Rust or tan spotting']), [])
    expect(results[0].issue.slug).toBe('magnesium-deficiency')
    expect(results[0].confidence).toBe('Moderate')
  })

  it('requires laboratory confirmation for viroid differentials', () => {
    const results = rankDifferentials(issues, context(['Short internodes', 'Brittle stems or leaves', 'Stunted growth']), [])
    expect(results[0].issue.slug).toBe('hop-latent-viroid')
    expect(results[0].missing).toContain('validated laboratory test')
  })
})
