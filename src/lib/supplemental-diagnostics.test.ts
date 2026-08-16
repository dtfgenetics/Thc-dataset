import { describe, expect, it } from 'vitest'
import { supplementalIssues } from '../data/supplemental-issues'
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

describe('supplemental diagnostic ranking', () => {
  it('keeps Fusarium low without root/crown evidence and applies controlled confirmation policy', () => {
    const results = rankDifferentials(
      supplementalIssues,
      context([
        'Dark sunken crown lesions extend upward from the cannabis root zone',
        'Reddish-brown or dark internal stem discoloration originates at the crown',
        'Roots are necrotic while crown tissue is darkened or rotted',
      ]),
      [],
    )

    expect(results[0].issue.slug).toBe('fusarium-crown-root-rot')
    expect(results[0].confidence).toBe('Low')
    expect(results[0].missing).toContain('root or crown view')
    expect(results[0].missing).toContain('confirmation: root/crown evidence')
    expect(results[0].missing).toContain('confirmation: isolation/microscopy/PCR/sequence')
  })

  it('ranks cannabis aphid above rice root aphid when foliage colonies are directly observed', () => {
    const results = rankDifferentials(
      supplementalIssues,
      context([
        'Colonies of small soft-bodied aphids are visible on cannabis leaves or stems',
        'Aphid cast skins or sticky honeydew occur near an active colony',
        'New growth is stressed in the same areas where aphids are actively feeding',
      ]),
      [],
    )

    expect(results[0].issue.slug).toBe('cannabis-aphid')
  })

  it('ranks rice root aphid when the discriminating evidence is root-associated', () => {
    const results = rankDifferentials(
      supplementalIssues,
      context([
        'Aphid colonies are visible on cannabis roots after careful root-zone inspection',
        'Winged aphids emerge from or cluster around the growing medium while root colonies are present',
        'Root-associated aphids are documented while stems and leaf undersides lack the typical cannabis-aphid colony pattern',
      ]),
      [],
    )

    expect(results[0].issue.slug).toBe('rice-root-aphid')
  })

  it('keeps salinity as a measured root-zone hypothesis rather than a visual-only high-confidence call', () => {
    const results = rankDifferentials(
      supplementalIssues,
      context([
        'Measured irrigation or root-zone EC is elevated relative to the established crop baseline while growth declines',
        'Growth suppression occurs together with a documented saline or high-salt root-zone exposure',
        'Leaf nutrient imbalance appears after a measured salinity increase rather than an isolated single-element withholding pattern',
      ], { ec: '3.2 mS/cm', watering: 'Automated irrigation' }),
      [],
    )

    expect(results[0].issue.slug).toBe('salinity-high-ec-stress')
    expect(results[0].confidence).not.toBe('High')
    expect(results[0].missing).toContain('measured pH')
  })

  it('keeps drought tied to water-status evidence and requests missing chemistry/context checks', () => {
    const results = rankDifferentials(
      supplementalIssues,
      context([
        'Substrate or soil moisture is measurably below the established irrigation target while the plant shows water-deficit stress',
        'Canopy wilt or reduced expansion coincides with a documented dry root zone and improves after appropriate rehydration',
        'Leaf area or biomass growth declines during a sustained measured water deficit without root rot evidence',
      ], { watering: 'Hand-water by dryback' }),
      [],
    )

    expect(results[0].issue.slug).toBe('drought-water-deficit-stress')
    expect(results[0].confidence).not.toBe('High')
    expect(results[0].missing).toContain('measured pH')
    expect(results[0].missing).toContain('measured EC/PPM')
  })
})
