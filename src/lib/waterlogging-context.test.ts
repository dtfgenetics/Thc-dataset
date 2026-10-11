import { describe, expect, it } from 'vitest'
import { issues } from '../data/catalog'

describe('waterlogging event and recovery context', () => {
  it('keeps repeated-event evidence separate from image-only confirmation and safe-duration claims', () => {
    const record = issues.find((item) => item.slug === 'overwatering-root-hypoxia')!
    const source = record.sources.find((item) => item.doi === '10.25959/23249576')!
    expect(source).toBeDefined()
    expect(source.publicationDate).toBe('2023-05-28')
    expect(source.supportedClaims?.join(' ')).toMatch(/unpublished thesis.*public abstract/)
    expect(source.supportedClaims?.join(' ')).toMatch(/experiment-specific.*not diagnostic thresholds/)
    expect(record.progression.find((item) => item.stage === 'Repeated exposure')?.description)
      .toMatch(/each flooding event.*recovery interval.*does not establish.*safe interval/)
    expect(record.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record.media).toEqual([])
    expect(record.confirmation.join(' ')).toMatch(/calibrated.*oxygen|oxygen.*calibrated/)
  })
})
