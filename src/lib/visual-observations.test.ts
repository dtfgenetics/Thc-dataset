import { describe, expect, it } from 'vitest'
import { visualIndicatorVocabulary } from './visual-observations'

describe('visualIndicatorVocabulary', () => {
  it('keeps visible symptom descriptions available to the image observation model', () => {
    const input = [
      'Older leaves yellow between green veins',
      'Small tan necrotic regions develop within advanced interveinal chlorosis',
      'Roots are visibly brown and sloughing',
    ]

    expect(visualIndicatorVocabulary(input)).toEqual(input)
  })

  it('removes indicators that require measurements, tissue analysis, or laboratory confirmation', () => {
    const input = [
      'Older leaves yellow between green veins',
      'Low magnesium is documented in correctly positioned foliage and linked to supply or root-zone availability',
      'Measured root-zone pH is outside the supported range',
      'Tissue analysis confirms low manganese',
      'RT-qPCR confirms the viroid',
      'Electrical conductivity is elevated',
    ]

    expect(visualIndicatorVocabulary(input)).toEqual(['Older leaves yellow between green veins'])
  })

  it('deduplicates the visual vocabulary before it is sent to the provider', () => {
    expect(visualIndicatorVocabulary(['Visible spotting', 'Visible spotting'])).toEqual(['Visible spotting'])
  })
})
