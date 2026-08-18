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
    expect(mo.photoOnlyMaxConfidence).toBeLessThanOrEqual(0.05)
    expect(mo.warnings.join(' ').toLowerCase()).toContain('no visual symptoms')
    expect(mo.confirmation.join(' ').toLowerCase()).toContain('photograph cannot confirm')
  })

  it('keeps Fusarium flower/head disease separate from the root/crown profile', () => {
    const flower = bySlug('fusarium-foliar-flower-head-blight')
    const root = bySlug('fusarium-crown-root-rot')
    expect(flower.id).not.toBe(root.id)
    expect(flower.affectedParts).toContain('flowers')
    expect(root.affectedParts.some((part) => part.toLowerCase().includes('root'))).toBe(true)
  })
})
