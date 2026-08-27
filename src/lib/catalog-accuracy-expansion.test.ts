import { describe, expect, it } from 'vitest'
import { categoryOrder, issues } from '../data/catalog'

const bySlug = (slug: string) => {
  const record = issues.find((item) => item.slug === slug)
  if (!record) throw new Error(`Missing diagnostic profile: ${slug}`)
  return record
}

describe('canonical diagnostic catalog accuracy expansion', () => {
  it('contains the expanded evidence-backed diagnostic baseline without duplicate ids or slugs', () => {
    expect(issues.length).toBeGreaterThanOrEqual(54)
    expect(new Set(issues.map((item) => item.id)).size).toBe(issues.length)
    expect(new Set(issues.map((item) => item.slug)).size).toBe(issues.length)
  })

  it('normalizes the rice root aphid DOI in the same catalog consumed by the app and exporter', () => {
    const source = bySlug('rice-root-aphid').sources.find((item) => item.title.includes('Rice Root Aphid'))
    expect(source?.doi).toBe('10.1093/jipm/pmaa008')
    expect(source?.url).toBe('https://doi.org/10.1093/jipm/pmaa008')
    expect(source?.publicationDate).toBe('2020-07-20')
  })

  it('normalizes the verified Septoria cannabicola DOI', () => {
    const source = bySlug('septoria-leaf-spot').sources.find((item) => item.title.startsWith('Septoria cannabicola'))
    expect(source?.doi).toBe('10.47371/mycosci.2023.1.004')
    expect(source?.url).toBe('https://doi.org/10.47371/mycosci.2023.1.004')
    expect(source?.publicationDate).toBe('2024-03-02')
  })

  it('keeps Septoria labels plant-linked, species-aware, and visually conservative', () => {
    const record = bySlug('septoria-leaf-spot')
    const evidence = [...record.indicators, ...record.exclusions, ...record.confirmation, ...record.warnings].join(' ').toLowerCase()
    const kentucky = record.sources.find((item) => item.doi === '10.1094/PDIS-12-20-2620-SC')
    const japan = record.sources.find((item) => item.doi === '10.47371/mycosci.2023.1.004')

    expect(record.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.25)
    expect(record.indicators.length).toBeGreaterThanOrEqual(8)
    expect(record.exclusions.length).toBeGreaterThanOrEqual(10)
    expect(record.progression.length).toBeGreaterThanOrEqual(5)
    expect(record.lookAlikes.length).toBeGreaterThanOrEqual(14)
    expect(record.confirmation.length).toBeGreaterThanOrEqual(8)
    expect(record.sources).toHaveLength(5)
    expect(kentucky?.authors).toHaveLength(6)
    expect(japan?.authors).toHaveLength(5)
    expect(evidence).toContain('different phylogenetic clades')
    expect(evidence).toContain('generic pcr')
    expect(evidence).toContain('human review')
    expect(record.sources.some((item) => item.doi === '10.1094/PHP-04-25-0127-RS')).toBe(true)
    expect(record.sources.some((item) => item.organization.includes('Cornell University'))).toBe(true)
    expect(record.media).toHaveLength(0)
  })

  it('classifies Cannabis downy mildew as an oomycete rather than a true fungus', () => {
    expect(categoryOrder).toContain('Oomycete pathogen')
    expect(bySlug('downy-mildew-pseudoperonospora').category).toBe('Oomycete pathogen')
  })

  it('contains a distinct nematode category for root-knot nematodes', () => {
    expect(categoryOrder).toContain('Nematode')
    expect(bySlug('root-knot-nematodes').category).toBe('Nematode')
  })

  it('prevents an image-only molybdenum deficiency phenotype from becoming a confident diagnosis', () => {
    const mo = bySlug('molybdenum-low-analytical-no-visual-phenotype')
    const evidenceText = [
      mo.summary,
      ...mo.progression.map((item) => item.description),
      ...mo.confirmation,
      ...mo.warnings,
    ].join(' ').toLowerCase()
    expect(mo.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.05)
    expect(evidenceText).toContain('no visual symptoms')
    expect(mo.confirmation.join(' ').toLowerCase()).toContain('photograph cannot confirm')
    expect(mo.indicators.length).toBeGreaterThanOrEqual(8)
    expect(mo.exclusions.length).toBeGreaterThanOrEqual(8)
    expect(mo.progression.length).toBeGreaterThanOrEqual(4)
    expect(mo.lookAlikes.length).toBeGreaterThanOrEqual(12)
    expect(mo.confirmation.length).toBeGreaterThanOrEqual(7)
    expect(mo.sources).toHaveLength(3)
    expect(mo.sources.some((source) => source.url === 'https://pubs.nmsu.edu/_a/A123/')).toBe(true)
    expect(mo.sources.some((source) => source.url === 'https://ask.ifas.ufl.edu/publication/EP081')).toBe(true)
    expect(mo.warnings.join(' ').toLowerCase()).toContain('human review')
    expect(mo.media).toHaveLength(0)
  })

  it('keeps Fusarium flower/head disease separate from the root/crown profile', () => {
    const flower = bySlug('fusarium-foliar-flower-head-blight')
    const root = bySlug('fusarium-crown-root-rot')
    expect(flower.id).not.toBe(root.id)
    expect(flower.affectedParts).toContain('flowers')
    expect(root.affectedParts.some((part) => part.toLowerCase().includes('root'))).toBe(true)
  })

  it('keeps Fusarium flower/head labels plant-linked, multi-species, and visually conservative', () => {
    const record = bySlug('fusarium-foliar-flower-head-blight')
    const evidence = [...record.indicators, ...record.exclusions, ...record.confirmation, ...record.warnings].join(' ').toLowerCase()
    const naturalInflorescenceStudy = record.sources.find((item) => item.doi === '10.3390/jof11070528')
    const kentuckyFlowerReport = record.sources.find((item) => item.doi === '10.1094/PDIS-06-21-1292-PDN')
    const media = record.media.find((item) => item.id === 'media-fusarium-flower-bud-figure-1')

    expect(record.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.25)
    expect(record.indicators.length).toBeGreaterThanOrEqual(8)
    expect(record.exclusions.length).toBeGreaterThanOrEqual(10)
    expect(record.progression.length).toBeGreaterThanOrEqual(5)
    expect(record.lookAlikes.length).toBeGreaterThanOrEqual(14)
    expect(record.confirmation.length).toBeGreaterThanOrEqual(7)
    expect(record.sources).toHaveLength(5)
    expect(evidence).toContain('latent detection')
    expect(evidence).toContain('detached-flower')
    expect(evidence).toContain('mycotoxin')
    expect(evidence).toContain('human review')
    expect(naturalInflorescenceStudy?.authors).toEqual(['Zamir K. Punja', 'Sheryl A. Tittlemier', 'Sean Walkowiak'])
    expect(kentuckyFlowerReport?.authors).toHaveLength(6)
    expect(media?.displayPermission).toBe('permitted')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.hostContext).toBe('cannabis')
  })

  it('keeps Exserohilum image-only labels conservative and linked to organism confirmation', () => {
    const record = bySlug('exserohilum-helminthosporium-leaf-blight')
    const evidence = [...record.indicators, ...record.exclusions, ...record.confirmation, ...record.warnings].join(' ').toLowerCase()
    const primary = record.sources.find((item) => item.doi === '10.1094/PDIS-08-18-1434-PDN')
    const media = record.media.find((item) => item.id === 'media-exserohilum-industrial-hemp-ncsu-license-review')

    expect(record.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.3)
    expect(record.progression.length).toBeGreaterThanOrEqual(5)
    expect(evidence).toContain('its1')
    expect(evidence).toContain('rpb2')
    expect(evidence).toContain('human review')
    expect(primary?.authors).toEqual(['Lindsey D. Thiessen', 'Tyler Schappe'])
    expect(primary?.publicationDate).toBe('2019-04-03')
    expect(media?.trainingEligible).toBe(false)
    expect(media?.trainingPermission).toBe('not-permitted')
    expect(media?.displayPermission).toBe('unknown')
    expect(media?.sourceUrl).toBe('https://plantpathology.ces.ncsu.edu/news/exserohilum-leaf-spot-causing-problems-in-nc-hemp/')
  })

  it('requires plant-linked evidence for Rhizoctonia and keeps symptom-only media out of training', () => {
    const record = bySlug('rhizoctonia-sore-shin-root-rot')
    const evidence = [...record.indicators, ...record.exclusions, ...record.confirmation, ...record.warnings].join(' ').toLowerCase()
    const compendium = record.sources.find((item) => item.doi === '10.1094/9780890546284.02.15.1')
    const handbook = record.sources.find((item) => item.url.includes('rhizoctonia-soreshin-root-rot'))

    expect(record.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.2)
    expect(record.progression.length).toBeGreaterThanOrEqual(5)
    expect(record.exclusions.length).toBeGreaterThanOrEqual(8)
    expect(record.lookAlikes.length).toBeGreaterThanOrEqual(12)
    expect(record.confirmation.length).toBeGreaterThanOrEqual(7)
    expect(evidence).toContain('right-angle')
    expect(evidence).toContain('human review')
    expect(compendium?.year).toBe(2022)
    expect(handbook?.year).toBe(2026)
    expect(record.media).toHaveLength(0)
  })
})
