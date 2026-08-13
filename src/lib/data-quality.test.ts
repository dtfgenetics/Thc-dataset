import { describe, expect, it } from 'vitest'
import { issues } from '../data/issues'
import { isDisplayableMedia } from './media'

describe('diagnostic dataset quality gates', () => {
  it('keeps identifiers and slugs unique', () => {
    expect(new Set(issues.map((issue) => issue.id)).size).toBe(issues.length)
    expect(new Set(issues.map((issue) => issue.slug)).size).toBe(issues.length)
  })

  it('maps reviewed records to dated, claim-level sources', () => {
    const reviewed = issues.filter((issue) => issue.reviewStatus === 'reviewed')
    for (const issue of reviewed) {
      expect(issue.sources.length, `${issue.slug} has no source`).toBeGreaterThan(0)
      for (const source of issue.sources) {
        expect(source.url, `${issue.slug} has a source without a URL`).toMatch(/^https:\/\//)
        expect(source.accessedDate, `${issue.slug} has an undated source check`).toMatch(/^\d{4}-\d{2}-\d{2}$/)
        expect(source.supportedClaims.length, `${issue.slug} has no source-to-claim mapping`).toBeGreaterThan(0)
      }
    }
  })

  it('requires provenance, licensing, and explicit training status for every media record', () => {
    for (const issue of issues) {
      for (const media of issue.media) {
        expect(media.sourceUrl, `${media.id} is missing its landing page`).toMatch(/^https:\/\//)
        expect(media.url ?? media.thumbnailUrl, `${media.id} is missing an asset URL`).toMatch(/^https:\/\//)
        expect(media.creator, `${media.id} is missing its creator`).toBeTruthy()
        expect(media.license, `${media.id} is missing its license`).toBeTruthy()
        expect(media.requiredAttribution, `${media.id} is missing attribution instructions`).toBeTruthy()
        expect(media.diagnosticLabel, `${media.id} is missing its diagnostic label`).toContain(issue.slug)
        expect(media.hostSpecies, `${media.id} is missing host-species context`).toBeTruthy()
        expect(['cannabis', 'non-cannabis', 'organism-only']).toContain(media.hostContext)
        expect(media.useLimitations.length, `${media.id} is missing use limitations`).toBeGreaterThan(0)
        expect(['permitted', 'not-permitted', 'unknown']).toContain(media.displayPermission)
        expect(['permitted', 'not-permitted', 'unknown']).toContain(media.trainingPermission)
        if (media.reviewStatus === 'approved-reference' || media.reviewStatus === 'approved-training') {
          expect(media.sha256, `${media.id} is missing its verified asset hash`).toMatch(/^[a-f0-9]{64}$/)
          expect(media.perceptualHash, `${media.id} is missing its perceptual hash`).toMatch(/^dhash64:[a-f0-9]{16}$/)
          expect(media.width, `${media.id} is missing its verified width`).toBeGreaterThan(0)
          expect(media.height, `${media.id} is missing its verified height`).toBeGreaterThan(0)
        }
        if (media.trainingEligible) {
          expect(media.trainingPermission).toBe('permitted')
          expect(media.reviewStatus).toBe('approved-training')
        }
        if (media.displayPermission !== 'permitted') {
          expect(isDisplayableMedia(media)).toBe(false)
          expect(media.trainingEligible).toBe(false)
        }
        if (media.hostContext === 'non-cannabis') {
          expect(media.confirmation).toBe('illustrative')
          expect(media.trainingEligible).toBe(false)
        }
      }
    }
  })

  it('keeps media identifiers and verified asset hashes unique', () => {
    const media = issues.flatMap((issue) => issue.media)
    expect(new Set(media.map((item) => item.id)).size).toBe(media.length)
    const hashes = media.flatMap((item) => item.sha256 ? [item.sha256] : [])
    expect(new Set(hashes).size).toBe(hashes.length)
    const perceptualHashes = media.flatMap((item) => item.perceptualHash ? [item.perceptualHash] : [])
    expect(new Set(perceptualHashes).size).toBe(perceptualHashes.length)
  })

  it('keeps bacterial diagnoses laboratory-bounded and image labels non-definitive', () => {
    const bacterial = issues.filter((issue) => issue.category === 'Bacterial pathogen')
    for (const issue of bacterial) {
      expect(issue.confirmation.join(' ').toLowerCase()).toContain('laboratory')
      expect(issue.warnings.join(' ').toLowerCase()).toMatch(/photograph|image|video/)
      expect(issue.warnings.join(' ').toLowerCase()).toMatch(/cannot confirm|not.*ground-truth/)
    }
  })

  it('keeps phytoplasma and Spiroplasma syndromes molecularly bounded', () => {
    const mollicutes = issues.filter((issue) => issue.category === 'Phytoplasma / Spiroplasma')
    for (const issue of mollicutes) {
      expect(issue.confirmation.join(' ').toLowerCase()).toMatch(/laboratory|molecular/)
      expect(issue.warnings.join(' ').toLowerCase()).toMatch(/image-only|visual diagnosis|not a species-level/)
      expect(issue.lookAlikes).toContain('Beet curly top virus disease')
    }
  })

  it('keeps reproductive-sex labels tied to visible flower organs and repeated inspection', () => {
    const record = issues.find((issue) => issue.slug === 'cannabis-reproductive-sex-expression')
    expect(record).toBeDefined()
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/seedling.*not reliable|seedling.*not.*ground-truth/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/reproductive|stigma|anther/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/repeat inspection|serial/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/chromosomal sex|genetic/)
  })
})
