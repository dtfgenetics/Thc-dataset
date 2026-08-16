import type { MediaRecord } from '../types'

export const verifiedReferenceMediaBatch2BySlug: Record<string, MediaRecord[]> = {
  'two-spotted-spider-mites': [
    {
      id: 'media-two-spotted-spider-mite-hemp-figure-1',
      url: 'https://mdpi-res.com/d_attachment/agronomy/agronomy-16-00651/article_deploy/html/images/agronomy-16-00651-g001.png',
      alt: 'Standardized flowering-hemp damage scale for two-spotted spider mites from no visible injury through stippling, chlorosis, necrosis, and dense webbing.',
      caption: 'Standardized 0–5 two-spotted spider mite damage scale on hemp, from no visible damage to extensive necrosis and webbing (Thweatt et al. 2026, Figure 1).',
      creator: 'Ivy N. Thweatt and Katelyn Kesheimer; figure included in the article with consent',
      license: 'CC BY 4.0',
      sourceUrl: 'https://doi.org/10.3390/agronomy16060651',
      mediaType: 'image',
      requiredAttribution: 'Thweatt IN, Saleem M, Xu J, Zebelo S, Ajayi OS. 2026. Cultivar Identity and Spider Mite Herbivory Shape Rhizosphere Bacteria in Hemp (Cannabis sativa L.). Agronomy 16(6):651. Figure 1 from Ivy N. Thweatt and Katelyn Kesheimer, included with consent. CC BY 4.0.',
      diagnosticLabel: 'two-spotted-spider-mites — Tetranychus urticae damage severity scale on flowering hemp',
      hostSpecies: 'Cannabis sativa',
      hostContext: 'cannabis',
      useLimitations: [
        'Damage-scale composite; reference-only as a whole figure.',
        'Stippling, chlorosis, necrosis, and webbing support mite injury but species-level attribution still requires direct mite/egg evidence.',
        'Do not treat the six severity panels as independent training examples until panel-level crop, source-group, and label review are complete.',
      ],
      displayPermission: 'permitted',
      reviewStatus: 'approved-reference',
      trainingPermission: 'permitted',
      sha256: 'dcde792626693321579109e4698605a8606e83c2fcdbdf16446fa4bba2a1dfa6',
      perceptualHash: 'dhash64:d2129296869696b6',
      width: 1455,
      height: 1340,
      view: 'diagram',
      stage: 'flower',
      severity: '0–5 damage scale',
      confirmation: 'expert-reviewed',
      trainingEligible: false,
    },
  ],
}
