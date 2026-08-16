import type { IssueRecord, SourceRecord } from '../types'

const source = (record: SourceRecord) => record

const bctvMolecularDiagnostics = source({
  title: 'Challenges to Cannabis sativa Production from Pathogens and Microbes—The Role of Molecular Diagnostics and Bioinformatics',
  organization: 'International Journal of Molecular Sciences',
  url: 'https://doi.org/10.3390/ijms25010014',
  authors: ['Zamir K. Punja', 'Dieter Kahl', 'Ron Reade', 'Yu Xiang', 'Jack Munz', 'Punya Nachappa'],
  publisher: 'MDPI',
  publicationDate: '2023-12-19',
  year: 2024,
  accessedDate: '2026-08-16',
  doi: '10.3390/ijms25010014',
  supportedClaims: [
    'Beet curly top virus was documented in symptomatic indoor- and outdoor-grown Cannabis plants across multiple genotypes and confirmed by RT-PCR in the molecular-diagnostics study.',
    'Reported Cannabis symptoms included combinations of severe stunting, reduced leaf size, leaf twisting/curling, deformation of new growth, mosaic/discoloration, and proliferation of small leaves on shortened branches; the exact visual pattern varied among genotypes.',
    'The source explicitly uses molecular diagnostics for BCTV confirmation, so the visual syndrome alone is not sufficient to confirm infection.',
  ],
})

export const virusIssues: IssueRecord[] = [
  {
    id: 'virus-bctv-cannabis',
    slug: 'beet-curly-top-virus',
    name: 'Beet curly top virus (BCTV) syndrome in Cannabis',
    scientificName: 'Beet curly top virus',
    category: 'Virus',
    severity: 'high',
    reviewStatus: 'reviewed',
    summary: 'A laboratory-bounded Cannabis virus syndrome associated with severe stunting, reduced leaf size, twisting/curling, distorted new growth, mosaic/discoloration, and short-branch leaf proliferation in documented cases. Visual appearance varies by genotype and cannot confirm BCTV without validated molecular testing.',
    affectedParts: ['new growth', 'leaves', 'shoots', 'whole canopy'],
    stages: ['vegetative', 'flower', 'all'],
    indicators: [
      'Severe stunting occurs together with reduced leaf size and distorted new growth',
      'New leaves show intense twisting, curling, or deformation that persists across successive nodes',
      'Mosaic or irregular discoloration accompanies leaf twisting and reduced growth',
      'Small leaves proliferate on shortened branches or compact shoots',
    ],
    exclusions: [
      'Validated BCTV testing is negative on an appropriately collected symptomatic sample',
      'The distortion is confined to directly damaged or sprayed tissue and new untreated growth resumes normally',
      'Microscopic pests, feeding injury, or visible organisms explain the distorted new growth better',
      'A measured nutrient, pH, EC, root-zone, heat, or light exposure tracks the syndrome and resolves after that exposure is corrected',
    ],
    progression: [
      { stage: 'Early', description: 'New growth becomes abnormally small, twisted, curled, or deformed; the pattern may initially resemble pest, chemical, nutritional, or developmental stress.' },
      { stage: 'Established syndrome', description: 'Stunting, reduced leaf size, mosaic/discoloration, and shortened-branch leaf proliferation may become more obvious, with genotype-dependent variation.' },
      { stage: 'Advanced impact', description: 'Persistent infection can be associated with substantial growth reduction and a chronically distorted canopy, but visual severity does not establish viral load or confirm BCTV.' },
    ],
    lookAlikes: [
      'Hop latent viroid',
      'Broad mite or hemp russet mite injury',
      'Chemical / spray phytotoxicity',
      'Genetic or developmental abnormality',
      'Root-zone pH or salinity stress',
    ],
    confirmation: [
      'Submit representative symptomatic tissue to a plant-diagnostic laboratory using a validated BCTV molecular assay such as RT-PCR/PCR appropriate to the laboratory method.',
      'When the result is unexpected or management decisions are high consequence, use sequence/amplicon confirmation or another validated laboratory method rather than relying on appearance alone.',
    ],
    immediateActions: [
      'Isolate strongly symptomatic propagation stock from clean mother and clone material while laboratory confirmation is pending.',
      'Document symptom distribution and preserve representative tissue before destructive corrective actions obscure the original syndrome.',
      'Inspect the crop for plausible vector or mechanical/spread pathways without assuming the vector is present solely because BCTV is suspected.',
    ],
    correctivePlan: [
      'Base culling, propagation, sanitation, and vector-management decisions on confirmed infection status and local crop-protection rules.',
      'Do not reuse symptomatic stock as clean propagation material unless BCTV has been ruled out by an appropriate diagnostic process.',
    ],
    prevention: [
      'Maintain clean propagation stock and separate newly introduced plant material until health status is established.',
      'Use routine vector scouting and exclusion practices appropriate to the production environment.',
      'Escalate persistent unexplained stunting/curling syndromes to laboratory testing rather than repeatedly changing nutrients or sprays.',
    ],
    warnings: [
      'Visual evidence cannot confirm BCTV infection.',
      'Leaf curl, mosaic, stunting, and small leaves are not unique to BCTV and overlap with mites, chemical injury, nutrient/root-zone stress, HLVd, and developmental disorders.',
      'Do not label a plant BCTV-positive, discard valuable genetics, or make broad crop decisions from a photograph alone.',
    ],
    sources: [bctvMolecularDiagnostics],
    media: [],
  },
]
