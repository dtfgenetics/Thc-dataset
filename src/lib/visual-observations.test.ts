import { afterEach, describe, expect, it, vi } from 'vitest'
import { requestVisualObservations, visualIndicatorVocabulary } from './visual-observations'
import type { EvidenceFile } from '../types'

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
    expect(visualIndicatorVocabulary([' Visible spotting ', 'Visible spotting', '   '])).toEqual(['Visible spotting'])
  })
})

describe('visual observation response contract', () => {
  afterEach(() => vi.unstubAllGlobals())
  const evidence = [{ file: new File(['image'], 'leaf.jpg', { type: 'image/jpeg' }), slot: 'close-up' }] as EvidenceFile[]
  const complete = {
    summary: 'Visible spotting', matchedIndicators: ['Visible spotting'], visibleFeatures: [],
    uncertainFeatures: [], qualityNotes: [], suggestedNextViews: [], unknownOrOutOfScope: false,
  }
  const serve = (payload: unknown) => vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => payload,
  }))

  it.each([null, [], {}, { ...complete, unknownOrOutOfScope: undefined }, { ...complete, visibleFeatures: 'invalid' }])(
    'rejects incomplete successful responses without treating uncertainty as resolved', async (payload) => {
      serve(payload)
      await expect(requestVisualObservations(evidence, ['Visible spotting'])).rejects.toThrow('incomplete response')
    },
  )

  it('keeps uncertain results informative without contributing symptom matches', async () => {
    serve({ ...complete, unknownOrOutOfScope: true, suggestedNextViews: ['Whole plant under neutral light'] })
    const result = await requestVisualObservations(evidence, ['Visible spotting'])
    expect(result.matchedIndicators).toEqual([])
    expect(result.suggestedNextViews).toEqual(['Whole plant under neutral light'])
  })

  it('normalizes matches and excludes duplicates and terms outside the controlled vocabulary', async () => {
    serve({ ...complete, matchedIndicators: ['Visible spotting ', 'Visible spotting', 'Confirmed pathogen'] })
    expect((await requestVisualObservations(evidence, [' Visible spotting '])).matchedIndicators).toEqual(['Visible spotting'])
  })
})
