import { categoryOrder, issues as coreIssues } from './issues'
import { supplementalIssues as rawSupplementalIssues } from './supplemental-issues'
import type { IssueRecord, MediaRecord } from '../types'

// Publisher verification on 2026-08-16 found one DOI typo in the first
// supplemental source batch. Normalize known source errata at the catalog
// boundary so the public app and QA/export layers never publish the stale value.
// The underlying supplemental file can be flattened into this corrected form
// during the next controlled data-file refactor.
const normalizeKnownSourceErrata = (issue: IssueRecord): IssueRecord => {
  if (issue.slug !== 'rice-root-aphid') return issue

  return {
    ...issue,
    sources: issue.sources.map((source) => source.title === 'Cannabis sativa as a Host of Rice Root Aphid (Hemiptera: Aphididae) in North America'
      ? {
          ...source,
          url: 'https://doi.org/10.1093/jipm/pmaa008',
          doi: '10.1093/jipm/pmaa008',
          publicationDate: '2020-07-20',
        }
      : source),
  }
}

const verifiedReferenceMediaBySlug: Record<string, MediaRecord[]> = {
  'rice-root-aphid': [
    {
      id: 'media-rice-root-aphid-cannabis-figure-2',
      url: 'https://oup.silverchair-cdn.com/oup/backfile/Content_public/Journal/jipm/11/1/10.1093_jipm_pmaa008/2/m_pmaa008f0002.jpeg?Expires=2147483647&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA&Signature=EPhu~pO~64p7GWKwLaeesO7JYfmMa8VpG5vqYu3ZxcGNwF4RdNFDEDOKBStsTpzEbph7z24JZxLSMtGslR7jMlrIlILt1UcCGx-Fnyt19QbE7xHClKmKI~qCVKVkjbXTWnBnVEtu9oUVGZdiWWD4SAO9ncgBncMgG1~Qh3cKeT6LT65KkdLoqRRDtwc0UU6riQgTj77ZsnuPdaXALAY5kAPxOwv1fVEZjnWJEcrAw3qygYI3bvDiIg0vF1UfSWUkiufo5KMGNkW1chR9j4IMsHkkoB6tE9ypcaSyRmoYdX5sKbjjeJmarUMy5LQJZGUSSqEQeOD7781Q5oWjw8UsXA__',
      alt: 'Rice root aphids visible at the base and roots of aeroponically grown Cannabis sativa.',
      caption: 'Rice root aphids living on the roots of aeroponically grown Cannabis sativa (Cranshaw and Wainwright-Evans 2020, Figure 2).',
      creator: 'Whitney Cranshaw and Suzanne Wainwright-Evans; figure photographer not separately stated in the caption',
      license: 'CC BY 4.0',
      sourceUrl: 'https://doi.org/10.1093/jipm/pmaa008',
      mediaType: 'image',
      requiredAttribution: 'Cranshaw W, Wainwright-Evans S. 2020. Cannabis sativa as a Host of Rice Root Aphid (Hemiptera: Aphididae) in North America. Journal of Integrated Pest Management 11(1):15. CC BY 4.0.',
      diagnosticLabel: 'Rice root aphid (Rhopalosiphum rufiabdominale) on Cannabis roots',
      hostSpecies: 'Cannabis sativa',
      hostContext: 'cannabis',
      useLimitations: [
        'Reference-only until source-group and panel-level training review are complete.',
        'The presence of rice root aphids is visible; generalized canopy decline is not uniquely diagnostic of this pest.',
        'Do not use this asset to infer root disease, nutrient status, or above-ground symptom severity.',
      ],
      displayPermission: 'permitted',
      reviewStatus: 'approved-reference',
      trainingPermission: 'permitted',
      sha256: '3fb068bfe723ed06c654bfcc96f990bfabdfa2e976a7770242325c7ae311dea4',
      perceptualHash: 'dhash64:19191b1a4e595b6b',
      width: 520,
      height: 403,
      view: 'root-crown',
      stage: 'all',
      severity: 'moderate',
      confirmation: 'expert-reviewed',
      trainingEligible: false,
    },
  ],
  'fusarium-crown-root-rot': [
    {
      id: 'media-fusarium-cannabis-figure-4',
      url: 'https://www.frontiersin.org/files/Articles/796062/xml-images/fagro-03-796062-g0004.webp',
      alt: 'Multi-panel reference figure showing Fusarium-associated disease signs and pathogen evidence on greenhouse-grown Cannabis plants.',
      caption: 'Infection of greenhouse-grown Cannabis plants by Fusarium species, including yellowing, crown infection and decay, pith necrosis, crown rot, diseased cuttings, flower infection, cultures, and pathogenicity-test symptoms (Gwinn et al. 2022, Figure 4).',
      creator: 'Zamir Punja (photographs), published in Gwinn et al. 2022',
      license: 'CC BY 4.0',
      sourceUrl: 'https://doi.org/10.3389/fagro.2021.796062',
      mediaType: 'image',
      requiredAttribution: 'Gwinn KD, Hansen Z, Kelly H, Ownley BH. 2022. Diseases of Cannabis sativa Caused by Diverse Fusarium Species. Frontiers in Agronomy 3:796062. Figure photographs courtesy of Zamir Punja. CC BY 4.0.',
      diagnosticLabel: 'Fusarium-associated Cannabis crown/root/wilt disease composite',
      hostSpecies: 'Cannabis sativa',
      hostContext: 'cannabis',
      useLimitations: [
        'Multi-panel and multi-species composite: reference-only as a whole figure.',
        'Do not treat the full composite as one single-class training example.',
        'Do not visually confirm a Fusarium species in an unknown plant from resemblance to this figure.',
        'Use the source article and laboratory confirmation guidance for causal identification.',
      ],
      displayPermission: 'permitted',
      reviewStatus: 'approved-reference',
      trainingPermission: 'permitted',
      sha256: 'a02abbebd496081013d34deb188640f3fc134a1ce3b0a77526ddd2babb576ebf',
      perceptualHash: 'dhash64:a7cd13d159c9cfcd',
      width: 1417,
      height: 1748,
      view: 'diagram',
      stage: 'all',
      severity: 'high',
      confirmation: 'expert-reviewed',
      trainingEligible: false,
    },
  ],
}

const enrichVerifiedReferenceMedia = (issue: IssueRecord): IssueRecord => {
  const verifiedMedia = verifiedReferenceMediaBySlug[issue.slug] ?? []
  if (!verifiedMedia.length) return issue
  return { ...issue, media: [...issue.media, ...verifiedMedia] }
}

export const supplementalIssues = rawSupplementalIssues
  .map(normalizeKnownSourceErrata)
  .map(enrichVerifiedReferenceMedia)

export const issues = [...coreIssues, ...supplementalIssues]

export { categoryOrder }

export const symptomOptions = Array.from(new Set(issues.flatMap((item) => item.indicators))).sort()
