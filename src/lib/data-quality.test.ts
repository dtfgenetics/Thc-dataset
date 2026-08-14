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

  it('keeps Botrytis bud-rot labels internal-view aware, laboratory-bounded, and license-safe', () => {
    const record = issues.find((issue) => issue.slug === 'botrytis-gray-mold-bud-rot')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/interior|internal/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/laboratory/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/not species-level ground truth|not.*ground truth/)
    expect(record?.lookAlikes).toContain('Fusarium flower mold or bud rot')
    expect(record?.lookAlikes).toContain('Normal pistil browning and late-flower senescence')
    expect(record?.media).toHaveLength(4)
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
    expect(record?.media.filter((item) => item.displayPermission !== 'permitted').every((item) => item.reviewStatus === 'license-review')).toBe(true)
  })

  it('keeps phosphorus deficiency tissue-confirmed, root-zone bounded, and composite-safe', () => {
    const record = issues.find((issue) => issue.slug === 'phosphorus-deficiency')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/tissue/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/ph.*ec|ec.*ph/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/root-zone|soil testing|substrate/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/not universal|not.*universal/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/purple.*not.*ground truth/)
    expect(record?.lookAlikes).toContain('Normal late-flower senescence')
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0]?.useLimitations.join(' ').toLowerCase()).toMatch(/three diagnosis classes/)
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
  })

  it('keeps calcium deficiency stage-aware, analytically bounded, and sequence-safe', () => {
    const record = issues.find((issue) => issue.slug === 'calcium-deficiency')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/upper and lower canopy|upper\/lower canopy/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/source water/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/root-zone.*ph.*ec/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/disagreed.*canopy location|location alone is not ground truth/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/three.*plants per treatment/)
    expect(record?.lookAlikes).toContain('Potassium deficiency')
    expect(record?.lookAlikes).toContain('Broad mite injury')
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0]?.useLimitations.join(' ').toLowerCase()).toMatch(/temporal sequence/)
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
  })

  it('keeps iron deficiency symptom-negative aware, analytically bounded, and composite-safe', () => {
    const record = issues.find((issue) => issue.slug === 'iron-deficiency')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/leaf tissue|tissue/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/ph.*ec|ec.*ph/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/no visible.*symptom|symptom absence cannot rule out/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/not universal|not.*universal/)
    expect(record?.lookAlikes).toContain('Manganese deficiency')
    expect(record?.lookAlikes).toContain('Light bleaching or heat stress')
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0]?.useLimitations.join(' ').toLowerCase()).toMatch(/two diagnosis classes/)
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
  })

  it('keeps boron toxicity exposure-confirmed, tissue-bounded, and composite-safe', () => {
    const record = issues.find((issue) => issue.slug === 'boron-toxicity')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/leaf tissue/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/source water|source-water/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/ph.*ec|ec.*ph/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/image-only ground truth/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/video.*no original asset url|no original asset url.*video/)
    expect(record?.lookAlikes).toContain('Potassium deficiency')
    expect(record?.media).toHaveLength(1)
    expect(record?.media[0]?.useLimitations.join(' ').toLowerCase()).toMatch(/two diagnosis classes/)
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
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

  it('keeps waterlogging diagnoses exposure-measured and pathogen-bounded', () => {
    const record = issues.find((issue) => issue.slug === 'overwatering-root-hypoxia')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/container weight|substrate-water|standing water/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/laboratory/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/image-only|photograph.*cannot/)
    expect(record?.lookAlikes).toContain('Water shortage or drought')
    expect(record?.lookAlikes.join(' ')).toMatch(/Pythium/)
  })

  it('keeps substrate-pH stress measured, medium-bounded, and non-visual', () => {
    const record = issues.find((issue) => issue.slug === 'acidic-extreme-substrate-ph-stress')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/actual substrate|root-zone ph/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/calibrated meter/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/alkalinity/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/ec/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/not a universal image phenotype|not.*universal.*image/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/peat-based.*not.*soil.*coco.*rockwool/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/fourfold micronutrients/)
    expect(record?.lookAlikes).toContain('Waterlogging or root-zone hypoxia')
    expect(record?.lookAlikes.join(' ')).toMatch(/Pythium/)
    expect(record?.media).toHaveLength(0)
  })

  it('keeps heat and light labels exposure-measured and cultivar-bounded', () => {
    const record = issues.find((issue) => issue.slug === 'heat-light-stress')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/ppfd/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/leaf temperature/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/root-zone|substrate water/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/nonspecific|not validated/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/universal.*threshold|not.*generalized/)
    expect(record?.lookAlikes).toContain('Hemp russet mite')
    expect(record?.lookAlikes).toContain('Normal late-flower senescence')
  })

  it('keeps thrips labels organism-confirmed and species-bounded', () => {
    const record = issues.find((issue) => issue.slug === 'thrips')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/tap.*white paper|collection tray/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/species-level.*laboratory|specialist/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/not.*ground truth/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/predatory thrips.*beneficial/)
    expect(record?.lookAlikes).toContain('Two-spotted spider mites')
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
  })

  it('keeps suspected genetic variegation exclusion-based and out of image-only ground truth', () => {
    const record = issues.find((issue) => issue.slug === 'genetic-variegation')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/do not confirm.*photograph|do not confirm.*video/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/virus\/viroid/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/genetic|meristem-lineage/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/mosaic symptom.*not evidence/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/one mother plant|sampled one mother plant/)
    expect(record?.lookAlikes).toContain('Hop latent viroid')
    expect(record?.media.every((item) => !item.trainingEligible)).toBe(true)
    expect(record?.media[0]?.useLimitations.join(' ').toLowerCase()).toMatch(/panel e.*panels a–d/)
  })

  it('keeps late-cycle leaf aging age-positioned and non-diagnostic from color', () => {
    const record = issues.find((issue) => issue.slug === 'normal-late-flower-fade')
    expect(record?.reviewStatus).toBe('reviewed')
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/do not label.*color.*photograph|do not label.*color.*video/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/leaf node|leaf age/)
    expect(record?.confirmation.join(' ').toLowerCase()).toMatch(/root-zone.*ph.*ec/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/remained green|visible yellowing is not required/)
    expect(record?.warnings.join(' ').toLowerCase()).toMatch(/not.*harvest|harvest.*not/)
    expect(record?.lookAlikes).toContain('Hop latent viroid')
    expect(record?.media).toHaveLength(0)
  })
})
