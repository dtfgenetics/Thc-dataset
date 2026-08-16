import { describe, expect, it } from 'vitest'
import { issues } from '../data/catalog'
import type { GrowContext } from '../types'
import { rankDifferentials } from './diagnostics'
import { isDisplayableMedia } from './media'

const context = (symptoms: string[]): GrowContext => ({
  stage: '',
  medium: '',
  ph: '',
  ec: '',
  watering: '',
  recentChanges: '',
  symptoms,
})

describe('BCTV Cannabis diagnostic profile', () => {
  const bctv = issues.find((issue) => issue.slug === 'beet-curly-top-virus')

  it('is a reviewed sourced virus profile with explicit laboratory confirmation limits', () => {
    expect(bctv).toBeTruthy()
    expect(bctv?.category).toBe('Virus')
    expect(bctv?.reviewStatus).toBe('reviewed')
    expect(bctv?.sources.length).toBeGreaterThan(0)
    expect(bctv?.indicators.length).toBeGreaterThanOrEqual(4)
    expect(bctv?.exclusions.length).toBeGreaterThanOrEqual(4)
    expect(bctv?.lookAlikes.length).toBeGreaterThanOrEqual(4)
    expect(bctv?.confirmation.join(' ').toLowerCase()).toMatch(/laboratory|molecular|rt-pcr|pcr/)
    expect(bctv?.warnings.join(' ').toLowerCase()).toMatch(/visual evidence cannot confirm|photograph alone/)
  })

  it('includes the reproducibly verified RT-PCR-confirmed Cannabis reference figure', () => {
    const media = bctv?.media.find((item) => item.id === 'media-bctv-cannabis-figure-19')
    expect(media).toBeTruthy()
    expect(media && isDisplayableMedia(media)).toBe(true)
    expect(media?.sha256).toBe('25decd9424d09359794823ac2357bb6b13e99d9f34247f4f1acfca6016343e90')
    expect(media?.perceptualHash).toBe('dhash64:1c9892b2985a7ab3')
    expect(media?.width).toBe(2686)
    expect(media?.height).toBe(1811)
    expect(media?.confirmation).toBe('lab-confirmed')
    expect(media?.trainingEligible).toBe(false)
  })

  it('keeps a strong visual BCTV-like symptom cluster low confidence until validated testing', () => {
    const results = rankDifferentials(
      issues,
      context([
        'Severe stunting occurs together with reduced leaf size and distorted new growth',
        'New leaves show intense twisting, curling, or deformation that persists across successive nodes',
        'Mosaic or irregular discoloration accompanies leaf twisting and reduced growth',
        'Small leaves proliferate on shortened branches or compact shoots',
      ]),
      [],
    )

    expect(results[0].issue.slug).toBe('beet-curly-top-virus')
    expect(results[0].confidence).toBe('Low')
    expect(results[0].missing).toContain('validated laboratory test')
  })
})
