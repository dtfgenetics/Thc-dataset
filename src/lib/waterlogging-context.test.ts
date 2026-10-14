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
    expect(record.media).toHaveLength(2)
    expect(record.media.map((item) => item.id)).toEqual([
      'media-waterlogging-cannabis-rwc-msi-lai-rincon-figure-2',
      'media-waterlogging-cannabis-gas-exchange-chlorophyll-rincon-figure-4',
    ])
    expect(record.media.every((item) => item.hostContext === 'cannabis')).toBe(true)
    expect(record.media.every((item) => item.view === 'diagram')).toBe(true)
    expect(record.media.every((item) => item.license?.includes('CC BY 4.0'))).toBe(true)
    expect(record.media.every((item) => item.displayPermission === 'permitted')).toBe(true)
    expect(record.media.every((item) => item.trainingPermission === 'permitted')).toBe(true)
    expect(record.media.every((item) => item.trainingEligible === false)).toBe(true)
    expect(record.media.every((item) => item.useLimitations.join(' ').toLowerCase().includes('reference-only'))).toBe(true)
    expect(record.confirmation.join(' ')).toMatch(/calibrated.*oxygen|oxygen.*calibrated/)
  })
})
