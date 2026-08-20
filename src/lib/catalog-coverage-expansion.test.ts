import { describe, expect, it } from 'vitest'
import { issues } from '../data/catalog'

const bySlug = (slug: string) => {
  const record = issues.find((item) => item.slug === slug)
  if (!record) throw new Error(`Missing diagnostic profile: ${slug}`)
  return record
}

describe('61-profile evidence-backed coverage expansion', () => {
  it('holds the expanded unique profile baseline', () => {
    expect(issues.length).toBeGreaterThanOrEqual(61)
    expect(new Set(issues.map((item) => item.id)).size).toBe(issues.length)
    expect(new Set(issues.map((item) => item.slug)).size).toBe(issues.length)
  })

  it.each([
    'spotted-cucumber-beetle',
    'tarnished-plant-bug',
    'dectes-stem-borer',
    'cabbage-looper-hemp',
    'japanese-beetle-hemp',
    'armyworm-caterpillar-feeding',
    'white-root-rot-dematophora-necatrix',
  ])('contains evidence-backed profile %s', (slug) => {
    const profile = bySlug(slug)
    expect(profile.reviewStatus).toBe('reviewed')
    expect(profile.sources.length).toBeGreaterThan(0)
    expect(profile.confirmation.length).toBeGreaterThan(0)
    expect(profile.lookAlikes.length).toBeGreaterThan(0)
  })

  it('deepens Pythium species evidence without splitting visual look-alikes into false species classes', () => {
    const pythium = bySlug('pythium-root-rot')
    const dois = new Set(pythium.sources.map((source) => source.doi).filter(Boolean))
    expect(dois).toContain('10.1094/PDIS-12-17-1999-PDN')
    expect(dois).toContain('10.1094/PDIS-09-16-1249-PDN')
    expect(dois).toContain('10.1094/PDIS-02-21-0336-PDN')
    expect(dois).toContain('10.1094/PDIS-02-25-0435-PDN')
    expect(dois).toContain('10.1094/PDIS-07-25-1413-PDN')
    expect(pythium.warnings.join(' ').toLowerCase()).toContain('species differ')
  })

  it('deepens the Fusarium root/crown complex without pretending images resolve species', () => {
    const fusarium = bySlug('fusarium-crown-root-rot')
    const dois = new Set(fusarium.sources.map((source) => source.doi).filter(Boolean))
    expect(dois).toContain('10.1094/PDIS-08-21-1640-PDN')
    expect(dois).toContain('10.1094/PDIS-10-24-2067-PDN')
    expect(fusarium.warnings.join(' ').toLowerCase()).toContain('laboratory-confirmed species')
  })

  it('represents Sclerotinia as a multi-species white-mold/crown-rot complex', () => {
    const sclerotinia = bySlug('sclerotinia-white-mold')
    expect(sclerotinia.name).toContain('crown rot complex')
    expect(sclerotinia.scientificName).toContain('Sclerotinia minor')
    expect(sclerotinia.sources.some((source) => source.doi === '10.1094/PDIS-01-19-0088-PDN')).toBe(true)
  })

  it('keeps the downy-mildew canonical record internally consistent after taxonomy correction', () => {
    const downy = bySlug('downy-mildew-pseudoperonospora')
    expect(downy.category).toBe('Oomycete pathogen')
    expect(downy.summary.toLowerCase()).not.toContain('fungal-pathogen ui bucket')
    expect(downy.warnings.join(' ').toLowerCase()).not.toContain('temporary ui grouping')
  })

  it('keeps manganese toxicity analytical, source-calibrated, and out of visual ground truth', () => {
    const manganese = bySlug('manganese-toxicity')
    const confirmation = manganese.confirmation.join(' ').toLowerCase()
    const warnings = manganese.warnings.join(' ').toLowerCase()
    expect(manganese.reviewStatus).toBe('reviewed')
    expect(manganese.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.35)
    expect(confirmation).toContain('do not confirm manganese toxicity from an image or video')
    expect(confirmation).toContain('root-zone ph and ec')
    expect(confirmation).toContain('tissue sample')
    expect(warnings).toContain('47.88 mg/kg')
    expect(warnings).toContain('patterns differ')
    expect(warnings).toContain('mixed-class composite')
    expect(manganese.lookAlikes).toEqual(expect.arrayContaining(['Boron toxicity', 'Potassium deficiency', 'Salinity / high EC', 'Leaf-spot disease']))
    expect(manganese.media).toHaveLength(0)
  })

  it('keeps the hemp spider-mite scale licensed, composite-bounded, and out of training', () => {
    const mites = bySlug('two-spotted-spider-mites')
    const reference = mites.media.find((item) => item.id === 'media-two-spotted-spider-mite-hemp-figure-1')
    expect(reference).toBeDefined()
    expect(reference?.license).toContain('CC BY 4.0')
    expect(reference?.trainingPermission).toBe('permitted')
    expect(reference?.trainingEligible).toBe(false)
    expect(reference?.diagnosticLabel).toContain('Tetranychus urticae damage severity scale')
    expect(reference?.useLimitations.join(' ').toLowerCase()).toMatch(/composite|panels/)
  })

  it('keeps the Cannabis powdery-mildew comparison licensed and source-group bounded', () => {
    const powdery = bySlug('powdery-mildew')
    const reference = powdery.media.find((item) => item.id === 'media-powdery-mildew-cannabis-figure-2')
    expect(reference).toBeDefined()
    expect(reference?.license).toBe('CC BY 4.0')
    expect(reference?.trainingPermission).toBe('permitted')
    expect(reference?.trainingEligible).toBe(false)
    expect(reference?.sourceUrl).toBe('https://doi.org/10.3389/fagro.2021.720215')
    expect(reference?.useLimitations.join(' ').toLowerCase()).toMatch(/resistant panel.*negative training control/)
  })

  it('keeps the flowering nitrogen-deficiency sequence licensed and out of automated training', () => {
    const nitrogen = bySlug('nitrogen-deficiency')
    const reference = nitrogen.media.find((item) => item.id === 'mdpi-cannabis-nitrogen-deficiency-figure-2-flowering')
    expect(reference).toBeDefined()
    expect(reference?.license).toBe('CC BY 4.0')
    expect(reference?.trainingPermission).toBe('permitted')
    expect(reference?.trainingEligible).toBe(false)
    expect(reference?.sourceUrl).toBe('https://doi.org/10.3390/plants12030422')
    expect(reference?.useLimitations.join(' ').toLowerCase()).toMatch(/four panels.*separate view, tissue, stage, and severity annotation/)
  })
})
