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

  it('does not fabricate a diagnosis from growth stage or evidence-slot bonuses alone', () => {
    const record = fixtureIssue('stage-only-candidate', ['A defining symptom'], { stages: ['Flowering'] })
    const evidence = [
      { id: 'whole', file: {} as File, previewUrl: '', slot: 'whole-plant' as const, quality: 'good' as const, notes: [] },
      { id: 'close', file: {} as File, previewUrl: '', slot: 'close-up' as const, quality: 'good' as const, notes: [] },
    ]
    expect(rankDifferentials([record], context([], { stage: 'Flowering' }), evidence)).toEqual([])
  })

  it('records stage and relevant evidence bonuses as bounded context signals', () => {
    const record = fixtureIssue('mite-context', ['Visible stippling'], { category: 'Mite', stages: ['Flowering'] })
    const evidence = [{ id: 'underside', file: {} as File, previewUrl: '', slot: 'underside' as const, quality: 'good' as const, notes: [] }]
    const results = rankDifferentials([record], context(['Visible stippling'], { stage: 'Flowering' }), evidence)
    expect(results[0].contextSignals).toEqual(expect.arrayContaining([
      'reported growth stage matches this profile: Flowering',
      'a leaf-underside view is available for this arthropod hypothesis',
    ]))
  })

  it('records supplied pH and EC as review context without treating their presence as confirmation', () => {
    const record = fixtureIssue('nutrient-context', ['Interveinal chlorosis'], { category: 'Nutrient deficiency' })
    const withoutChemistry = rankDifferentials([record], context(['Interveinal chlorosis']), [])
    const withChemistry = rankDifferentials([record], context(['Interveinal chlorosis'], { ph: '6.2', ec: '1.4' }), [])
    expect(withChemistry[0].contextSignals).toContain('measured pH and EC/PPM were supplied for root-zone review; values are not treated as confirming by themselves')
    expect(withChemistry[0].score).toBe(withoutChemistry[0].score)
  })

  it('ranks magnesium deficiency without overstating confidence', () => {
    const results = rankDifferentials(issues, context(['Older leaves yellow between green veins', 'Rust or tan spotting']), [])
    expect(results[0].issue.slug).toBe('magnesium-deficiency')
    expect(results[0].confidence).toBe('Moderate')
    expect(results[0].missing).toContain('measured pH')
    expect(results[0].missing).toContain('measured EC/PPM')
  })

  it('keeps older/lower magnesium evidence ahead of an isolated upper-canopy iron-like sign', () => {
    const nutrientLookAlikes = issues.filter((issue) => ['magnesium-deficiency', 'iron-deficiency', 'manganese-deficiency'].includes(issue.slug))
    const results = rankDifferentials(nutrientLookAlikes, context([
      'Older leaves yellow between green veins',
      'The vegetative T1 sequence begins on lower and older foliage',
      'Interveinal chlorosis develops on new and expanding leaves while veins remain relatively greener',
    ]), [])

    expect(results[0].issue.slug).toBe('magnesium-deficiency')
    expect(results[0].supporting).toContain('The vegetative T1 sequence begins on lower and older foliage')
  })

  it('keeps upper-canopy iron evidence ahead of an isolated magnesium-like sign', () => {
    const nutrientLookAlikes = issues.filter((issue) => ['magnesium-deficiency', 'iron-deficiency', 'manganese-deficiency'].includes(issue.slug))
    const results = rankDifferentials(nutrientLookAlikes, context([
      'Interveinal chlorosis develops on new and expanding leaves while veins remain relatively greener',
      'Paling spreads through the upper half and is most apparent at the growing tip',
      'Older leaves yellow between green veins',
    ]), [])

    expect(results[0].issue.slug).toBe('iron-deficiency')
    expect(results[0].supporting).toContain('Paling spreads through the upper half and is most apparent at the growing tip')
  })

  it('keeps manganese netting and tan flecks distinct from magnesium and iron look-alikes', () => {
    const nutrientLookAlikes = issues.filter((issue) => ['magnesium-deficiency', 'iron-deficiency', 'manganese-deficiency'].includes(issue.slug))
    const results = rankDifferentials(nutrientLookAlikes, context([
      'Bright-yellow netted interveinal chlorosis develops on upper and central foliage in the T1 withholding study',
      'Chlorotic netting begins near the leaflet midrib and spreads outward toward margins',
      'Small tan necrotic regions develop within advanced interveinal chlorosis',
      'Interveinal chlorosis develops on new and expanding leaves while veins remain relatively greener',
    ]), [])

    expect(results[0].issue.slug).toBe('manganese-deficiency')
    expect(results[0].supporting).toHaveLength(3)
  })

  it('keeps viroid differentials low confidence until laboratory confirmation and applies the HLVd response policy', () => {
    const results = rankDifferentials(issues, context(['Short internodes', 'Brittle stems or leaves', 'Stunted growth']), [])
    expect(results[0].issue.slug).toBe('hop-latent-viroid')
    expect(results[0].missing).toContain('validated laboratory test')
    expect(results[0].missing).toContain('confirmation: RT-PCR')
    expect(results[0].missing).toContain('confirmation: RT-qPCR')
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
    expect(results[0].missing).toContain('confirmation: high-magnification organism or egg evidence')
    expect(results[0].missing).not.toContain('measured pH')
    expect(results[0].missing).not.toContain('measured EC/PPM')
  })

  it('keeps root-pathogen confidence low without a root or crown view and applies the Pythium policy', () => {
    const results = rankDifferentials(issues, context([
      'Plant-linked washed roots show expanding brown lesions, decay, and loss of normally pale active root tissue.',
      'Decayed roots may shed or slough the outer cortex and leave a thinner central vascular core; record texture and a scale rather than inferring slime from color alone.',
      'Stunting, chlorosis, wilt despite a moist root zone, necrosis, defoliation, or collapse can follow root or crown damage but are nonspecific secondary canopy signs.',
    ]), [])
    expect(results[0].issue.slug).toBe('pythium-root-rot')
    expect(results[0].confidence).toBe('Low')
    expect(results[0].missing).toContain('root or crown view')
    expect(results[0].missing).toContain('confirmation: root/crown evidence')
    expect(results[0].missing).toContain('confirmation: isolation/microscopy/PCR/sequence')
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

  it('rewards a candidate that explains a larger share of its defining indicators', () => {
    const shared = ['Shared sign 1', 'Shared sign 2']
    const records = [
      fixtureIssue('broad-profile', [...shared, 'Unseen sign 3', 'Unseen sign 4', 'Unseen sign 5', 'Unseen sign 6']),
      fixtureIssue('focused-profile', shared),
    ]
    const results = rankDifferentials(records, context(shared), [])
    expect(results[0].issue.slug).toBe('focused-profile')
    expect(results[0].score).toBeGreaterThan(results[1].score)
  })

  it('downgrades a high-scoring leader when a look-alike is essentially tied', () => {
    const records = [
      fixtureIssue('candidate-a', ['A specific sign 1', 'A specific sign 2', 'A specific sign 3']),
      fixtureIssue('candidate-b', ['B specific sign 1', 'B specific sign 2', 'B specific sign 3']),
    ]
    const results = rankDifferentials(records, context([
      'A specific sign 1', 'A specific sign 2', 'A specific sign 3',
      'B specific sign 1', 'B specific sign 2', 'B specific sign 3',
    ]), [])
    expect(results[0].confidence).toBe('Moderate')
    expect(results[0].missing).toContain('additional discriminating evidence between the leading look-alikes')
    expect(results[1].confidence).toBe('Moderate')
  })

  it('honors a conservative photo-only confidence cap when a record defines one', () => {
    const record = fixtureIssue('photo-capped', ['Distinct sign 1', 'Distinct sign 2', 'Distinct sign 3'], { photoOnlyMaxConfidence: 0.5 })
    const results = rankDifferentials([record], context(['Distinct sign 1', 'Distinct sign 2', 'Distinct sign 3']), [])
    expect(results[0].confidence).toBe('Low')
    expect(results[0].missing).toContain('response policy limits photo-only confidence')
  })

  it('uses controlled backend confirmation requirements for policy-bound canonical conditions', () => {
    const record = fixtureIssue('hlvd-policy-fixture', ['Short internodes', 'Brittle tissue', 'Stunted growth'], { canonicalId: 'CAN-DIS-011' })
    const results = rankDifferentials([record], context(['Short internodes', 'Brittle tissue', 'Stunted growth']), [])
    expect(results[0].confidence).toBe('Low')
    expect(results[0].missing).toContain('confirmation: RT-PCR')
    expect(results[0].missing).toContain('confirmation: RT-qPCR')
  })
})
