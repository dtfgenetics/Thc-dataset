import type { MediaRecord } from '../types'

export const verifiedReferenceMediaBatch3BySlug: Record<string, MediaRecord[]> = {
  thrips: [
    {
      id: 'media-thrips-hemp-bugwood-5569060',
      url: 'https://bugwoodcloud.org/images/1536x1024/5569060.jpg',
      alt: 'Severe onion-thrips feeding injury on a Cannabis sativa hemp leaf.',
      caption: 'Severe leaf injury to hemp produced by onion thrips (Thrips tabaci), Bugwood image 5569060.',
      creator: 'Whitney Cranshaw, Colorado State University, Bugwood.org',
      license: 'CC BY 3.0',
      sourceUrl: 'https://www.invasive.org/browse/detail.cfm?imgnum=5569060',
      mediaType: 'image',
      requiredAttribution: 'Whitney Cranshaw, Colorado State University, Bugwood.org, image 5569060. Licensed under CC BY 3.0.',
      diagnosticLabel: 'thrips — severe Thrips tabaci feeding injury on Cannabis sativa hemp',
      hostSpecies: 'Cannabis sativa',
      hostContext: 'cannabis',
      useLimitations: [
        'Reference-only feeding-damage image.',
        'Silvery or pale scars and speckling can overlap other pests or physical injury.',
        'Confirm thrips adults or larvae with magnification before making a species-level causal claim.',
      ],
      displayPermission: 'permitted',
      reviewStatus: 'approved-reference',
      trainingPermission: 'permitted',
      sha256: '04234384d5ab682600c748a65a62395adbf1cdfbe1f9489df43969025d53e54c',
      perceptualHash: 'dhash64:b3e78e80888094ca',
      width: 1536,
      height: 1152,
      view: 'affected-close-up',
      stage: 'all',
      severity: 'high',
      confirmation: 'expert-reviewed',
      trainingEligible: false,
    },
  ],
}
