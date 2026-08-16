import { categoryOrder, issues as rawCoreIssues } from './issues'
import { supplementalIssues as rawSupplementalIssues } from './supplemental-issues'
import type { IssueRecord, MediaRecord } from '../types'

// These mappings are not inferred from names. Each pair is directly supported by
// backend/config/diagnostic-response-policy.json, where the policy names exactly
// one canonical diagnosis ID. Ambiguous multi-ID policies remain unmapped here.
const controlledCoreIssueIds: Record<string, { canonicalId: string; responsePolicyId: string }> = {
  'hop-latent-viroid': { canonicalId: 'CAN-DIS-011', responsePolicyId: 'POL-HLVD' },
  'pythium-root-rot': { canonicalId: 'CAN-ROOT-002', responsePolicyId: 'POL-PYTHIUM' },
  'powdery-mildew': { canonicalId: 'CAN-DIS-001', responsePolicyId: 'POL-PM' },
  'botrytis-gray-mold-bud-rot': { canonicalId: 'CAN-DIS-002', responsePolicyId: 'POL-BOTRYTIS' },
  'two-spotted-spider-mites': { canonicalId: 'CAN-PEST-001', responsePolicyId: 'POL-SPIDER-MITE' },
  'acidic-extreme-substrate-ph-stress': { canonicalId: 'CAN-STRESS-006', responsePolicyId: 'POL-PH-LOCKOUT' },
}

const attachControlledCoreIds = (issue: IssueRecord): IssueRecord => {
  const mapping = controlledCoreIssueIds[issue.slug]
  return mapping ? { ...issue, ...mapping } : issue
}

// Publisher verification on 2026-08-16 found one DOI typo in the first
// supplemental source batch. Normalize known source errata at the catalog
// boundary so the public app and QA/export layers never publish the stale value.
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
      diagnosticLabel: 'rice-root-aphid — Rice root aphid (Rhopalosiphum rufiabdominale) on Cannabis roots',
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
      diagnosticLabel: 'fusarium-crown-root-rot — Fusarium-associated Cannabis crown/root/wilt disease composite',
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
  'cannabis-aphid': [
    {
      id: 'media-cannabis-aphid-figure-2',
      url: 'https://mdpi-res.com/d_attachment/plants/plants-14-00931/article_deploy/html/images/plants-14-00931-g002.png',
      alt: 'Cannabis plants infested with cannabis aphids alongside magnified adult and winged Phorodon cannabis.',
      caption: 'Cannabis plants of the Congo Durban variety infested with Phorodon cannabis, with adult and winged adult aphids shown under a stereo microscope at 20× magnification (Lopez Restrepo and Kovalchuk 2025, Figure 2).',
      creator: 'Daniel Lopez Restrepo and Igor Kovalchuk',
      license: 'CC BY 4.0',
      sourceUrl: 'https://doi.org/10.3390/plants14060931',
      mediaType: 'image',
      requiredAttribution: 'Lopez Restrepo D, Kovalchuk I. 2025. Investigating the Effects of Entomopathogenic Fungi on Mortality of Phorodon cannabis Populations in Cannabis Plants. Plants 14(6):931. CC BY 4.0.',
      diagnosticLabel: 'cannabis-aphid — Phorodon cannabis infestation and adult morphology on Cannabis sativa',
      hostSpecies: 'Cannabis sativa',
      hostContext: 'cannabis',
      useLimitations: [
        'Multi-panel plant-and-organism figure; reference-only as a whole image.',
        'Do not infer cannabis aphid from yellowing, wilting, or leaf distortion without directly observing aphids or other insect evidence.',
        'Keep training-ineligible until panel-level source grouping and crop review are complete.',
      ],
      displayPermission: 'permitted',
      reviewStatus: 'approved-reference',
      trainingPermission: 'permitted',
      sha256: '9e03540f970a4db0a8519a71c7773bc93d1221550e8a1ccf9190371e617ad012',
      perceptualHash: 'dhash64:6444daa9ad9b989a',
      width: 1623,
      height: 1724,
      view: 'diagram',
      stage: 'all',
      severity: 'moderate',
      confirmation: 'expert-reviewed',
      trainingEligible: false,
    },
  ],
  'powdery-mildew': [
    {
      id: 'media-powdery-mildew-cannabis-figure-2',
      url: 'https://www.frontiersin.org/files/Articles/720215/xml-images/fagro-03-720215-g0002.webp',
      alt: 'Cannabis powdery mildew experiment comparing a susceptible plant with dense powdery mycelial growth and a resistant phenotype without visible colonies.',
      caption: 'Cannabis powdery mildew resistance experiment showing a susceptible phenotype with dense mycelial growth beside a resistant phenotype without visible powdery mildew colonies (Mihalyov and Garfinkel 2021, Figure 2).',
      creator: 'Paul D. Mihalyov and Andrea R. Garfinkel',
      license: 'CC BY 4.0',
      sourceUrl: 'https://doi.org/10.3389/fagro.2021.720215',
      mediaType: 'image',
      requiredAttribution: 'Mihalyov PD, Garfinkel AR. 2021. Discovery and Genetic Mapping of PM1, a Powdery Mildew Resistance Gene in Cannabis sativa L. Frontiers in Agronomy 3:720215. CC BY 4.0.',
      diagnosticLabel: 'powdery-mildew — Cannabis powdery mildew susceptible/resistant phenotype comparison',
      hostSpecies: 'Cannabis sativa',
      hostContext: 'cannabis',
      useLimitations: [
        'Reference-only phenotype comparison from a controlled disease-resistance experiment.',
        'Dense white mycelial growth can strongly support powdery mildew, but organism identification remains separate when the causal species matters.',
        'Do not use the resistant panel as a negative training control without source-group and experimental-context review.',
      ],
      displayPermission: 'permitted',
      reviewStatus: 'approved-reference',
      trainingPermission: 'permitted',
      sha256: '7690fd41440735591b9e4562b00fdc58274577cbb3ea38f305f98c27474e6046',
      perceptualHash: 'dhash64:69accecc8edb638e',
      width: 1535,
      height: 1027,
      view: 'whole-plant',
      stage: 'vegetative',
      severity: 'moderate',
      confirmation: 'expert-reviewed',
      trainingEligible: false,
    },
  ],
  'pythium-root-rot': [
    {
      id: 'media-pythium-hemp-pathogenicity-figure-7',
      url: 'https://www.frontiersin.org/files/Articles/706138/xml-images/fagro-03-706138-g0007.webp',
      alt: 'Hemp plants from a controlled pathogenicity trial comparing Pythium, Globisporangium, Fusarium, and uninoculated treatments.',
      caption: "Hemp 'Wife' plants 14 days after inoculation with pathogenic Pythium myriotylum, Globisporangium irregulare, or Fusarium oxysporum isolates, plus the uninoculated control (McGehee and Raudales 2021, Figure 7).",
      creator: 'Cora S. McGehee and Rosa E. Raudales',
      license: 'CC BY 4.0',
      sourceUrl: 'https://doi.org/10.3389/fagro.2021.706138',
      mediaType: 'image',
      requiredAttribution: 'McGehee CS, Raudales RE. 2021. First Report of Pathogens Associated With Root Rot and Wilt of Cannabis sativa in Connecticut. Frontiers in Agronomy 3:706138. CC BY 4.0.',
      diagnosticLabel: 'pythium-root-rot — controlled hemp root-pathogen pathogenicity comparison including Pythium myriotylum',
      hostSpecies: 'Cannabis sativa',
      hostContext: 'cannabis',
      useLimitations: [
        'Multi-pathogen treatment composite; reference-only as a whole figure.',
        'Whole-plant chlorosis, wilt, and growth reduction are not Pythium-specific.',
        'Do not use this figure to visually confirm Pythium in an unknown plant; root/crown evidence and laboratory identification remain required.',
      ],
      displayPermission: 'permitted',
      reviewStatus: 'approved-reference',
      trainingPermission: 'permitted',
      sha256: '54267dc0fe3eccabaa8f5bd87cae3394beece60a21134bac7d765c0d1817d47b',
      perceptualHash: 'dhash64:e949555123865373',
      width: 2008,
      height: 1501,
      view: 'whole-plant',
      stage: 'vegetative',
      severity: 'high',
      confirmation: 'lab-confirmed',
      trainingEligible: false,
    },
  ],
}

const enrichVerifiedReferenceMedia = (issue: IssueRecord): IssueRecord => {
  const verifiedMedia = verifiedReferenceMediaBySlug[issue.slug] ?? []
  if (!verifiedMedia.length) return issue
  return { ...issue, media: [...issue.media, ...verifiedMedia] }
}

export const coreIssues = rawCoreIssues
  .map(attachControlledCoreIds)
  .map(enrichVerifiedReferenceMedia)
export const supplementalIssues = rawSupplementalIssues
  .map(normalizeKnownSourceErrata)
  .map(enrichVerifiedReferenceMedia)

export const issues = [...coreIssues, ...supplementalIssues]

export { categoryOrder }

export const symptomOptions = Array.from(new Set(issues.flatMap((item) => item.indicators))).sort()
