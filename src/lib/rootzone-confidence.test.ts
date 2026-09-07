import { describe, expect, it } from 'vitest'
import type { EvidenceFile, GrowContext, IssueRecord } from '../types'
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

const evidence: EvidenceFile[] = [
  { id: 'whole', file: {} as File, previewUrl: '', slot: 'whole-plant', quality: 'good', notes: [] },
  { id: 'close', file: {} as File, previewUrl: '', slot: 'close-up', quality: 'good', notes: [] },
  { id: 'roots', file: {} as File, previewUrl: '', slot: 'root-crown', quality: 'good', notes: [] },
]

const record = (slug: string): IssueRecord => ({
  id: slug,
  slug,
  name: slug,
  category: 'Water / root-zone',
  severity: 'moderate',
  reviewStatus: 'reviewed',
  summary: '',
  affectedParts: [],
  stages: [],
  indicators: ['Signal A', 'Signal B', 'Signal C'],
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
})

const symptoms = ['Signal A', 'Signal B', 'Signal C']

describe('root-zone structured evidence confidence gates', () => {
  it('keeps pH stress low until structured pH evidence is recorded', () => {
    const issue = record('acidic-extreme-substrate-ph-stress')
    const withoutPh = rankDifferentials([issue], context(symptoms, { ec: '1.4', watering: 'normal' }), evidence)[0]
    const withPh = rankDifferentials([issue], context(symptoms, { ph: '4.2', ec: '1.4', watering: 'normal' }), evidence)[0]

    expect(withoutPh.confidence).toBe('Low')
    expect(withoutPh.missing).toContain('structured root-zone pH measurement linked to this plant')
    expect(withPh.contextSignals).toContain('structured root-zone pH evidence is recorded for this exposure-dependent hypothesis')
  })

  it('keeps salinity/high-EC stress low until structured EC evidence is recorded', () => {
    const issue = record('salinity-high-ec-stress')
    const withoutEc = rankDifferentials([issue], context(symptoms, { ph: '6.2', watering: 'normal' }), evidence)[0]
    const withEc = rankDifferentials([issue], context(symptoms, { ph: '6.2', ec: '3.1', watering: 'normal' }), evidence)[0]

    expect(withoutEc.confidence).toBe('Low')
    expect(withoutEc.missing).toContain('structured root-zone EC/PPM measurement linked to this plant')
    expect(withEc.contextSignals).toContain('structured root-zone EC/PPM evidence is recorded for this exposure-dependent hypothesis')
  })

  it.each(['overwatering-root-hypoxia', 'drought-water-deficit-stress'])('keeps %s low until irrigation or moisture context is recorded', (slug) => {
    const issue = record(slug)
    const withoutWatering = rankDifferentials([issue], context(symptoms, { ph: '6.2', ec: '1.4' }), evidence)[0]
    const withWatering = rankDifferentials([issue], context(symptoms, { ph: '6.2', ec: '1.4', watering: 'measured substrate moisture trend recorded' }), evidence)[0]

    expect(withoutWatering.confidence).toBe('Low')
    expect(withoutWatering.missing).toContain('structured irrigation / substrate-moisture evidence linked to this plant')
    expect(withWatering.contextSignals).toContain('structured irrigation or substrate-moisture evidence is recorded for this exposure-dependent hypothesis')
  })
})
