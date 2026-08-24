import type { IssueRecord, SourceRecord } from '../types'

export interface EvidenceAugmentation {
  sources: SourceRecord[]
  patch?: Pick<Partial<IssueRecord>, 'name' | 'scientificName' | 'summary'>
  appendWarnings?: string[]
}

export const evidenceAugmentationsBySlug: Record<string, EvidenceAugmentation> = {
  'pythium-root-rot': {
    sources: [
      {
        title: 'First Report of Pythium ultimum Crown and Root Rot of Industrial Hemp in the United States', organization: 'Plant Disease',
        url: 'https://doi.org/10.1094/PDIS-12-17-1999-PDN', authors: ['Janna Beckerman', 'John Stone', 'Gail Ruhl', 'Tom Creswell'], publisher: 'American Phytopathological Society', publicationDate: '2018-08-08', year: 2018, accessedDate: '2026-08-24', doi: '10.1094/PDIS-12-17-1999-PDN',
        supportedClaims: ['Pythium ultimum was pathogenic to industrial hemp in replicated inoculation work; symptoms began within about one week and the organism was reisolated and PCR-confirmed.', 'Cool early planting, low-lying/flood-prone conditions, and soil crusting after intense rainfall were risk context in the report, not species-level visual identifiers.'],
      },
      {
        title: 'First Report of Pythium aphanidermatum Crown and Root Rot of Industrial Hemp in the United States', organization: 'Plant Disease',
        url: 'https://doi.org/10.1094/PDIS-09-16-1249-PDN', authors: ['Janna Beckerman', 'Hannah Nisonson', 'Nicolette Albright', 'Tom C. Creswell'], publisher: 'American Phytopathological Society', publicationDate: '2017-03-20', year: 2017, accessedDate: '2026-08-24', doi: '10.1094/PDIS-09-16-1249-PDN',
        supportedClaims: ['Industrial hemp with Pythium aphanidermatum crown/root rot showed chlorosis, stunting, wilt, brown root lesions, feeder-root loss, and sometimes brown water-soaked stem lesions.', 'The above-ground syndrome overlaps other root diseases and water stress, reinforcing the need for cleaned-root and laboratory evidence.'],
      },
      {
        title: 'First Report of Pythium myriotylum Causing Root Rot in Cannabis sativa in California', organization: 'Plant Disease',
        url: 'https://doi.org/10.1094/PDIS-02-21-0336-PDN', authors: ['Tera L. Pitman', 'Richard N. Philbrook', 'Jeremy G. Warren'], publisher: 'American Phytopathological Society', publicationDate: '2021-11-15', year: 2021, accessedDate: '2026-08-24', doi: '10.1094/PDIS-02-21-0336-PDN',
        supportedClaims: ['Greenhouse medical Cannabis with Pythium myriotylum root rot showed stunting, chlorosis, senescence, reduced root mass and root-hair density, and necrotic root lesions.', 'The Cannabis-specific phenotype does not make canopy appearance species-specific.'],
      },
      {
        title: 'First Report of Pythium aphanidermatum Causing Crown and Root Rot in Cannabis sativa in Florida', organization: 'Plant Disease',
        url: 'https://doi.org/10.1094/PDIS-02-25-0435-PDN', publisher: 'American Phytopathological Society', publicationDate: '2025-07-24', year: 2025, accessedDate: '2026-08-24', doi: '10.1094/PDIS-02-25-0435-PDN',
        supportedClaims: ['Pythium aphanidermatum crown/root rot has been confirmed in indoor Cannabis grown in rockwool across multiple cultivars in Florida.', 'Species occurrence across production systems supports retaining a Pythium complex label unless laboratory evidence resolves species.'],
      },
      {
        title: 'First Report of Pythium myriotylum Causing Damping off and Root Rot in Cannabis sativa in Florida', organization: 'Plant Disease',
        url: 'https://doi.org/10.1094/PDIS-07-25-1413-PDN', authors: ['Ashley Brown', 'Eden Blit', 'Sydney Gerstenberg', 'Krista Say', 'Richard Philbrook'], publisher: 'American Phytopathological Society', publicationDate: '2026-03-03', year: 2026, accessedDate: '2026-08-24', doi: '10.1094/PDIS-07-25-1413-PDN',
        supportedClaims: ['Pythium myriotylum was confirmed causing damping-off and root rot in indoor Cannabis cuttings from five cultivars in Florida.', 'The expanded cultivar evidence supports propagation-stage scouting and reinforces that Pythium disease can occur before a mature-plant canopy syndrome is available.'],
      },
      {
        title: 'Pathogenicity and Mefenoxam Sensitivity of Pythium, Globisporangium, and Fusarium Isolates From Coconut Coir and Rockwool in Marijuana (Cannabis sativa L.) Production',
        organization: 'Frontiers in Agronomy', url: 'https://doi.org/10.3389/fagro.2021.706138', authors: ['Cora S. McGehee', 'Rosa E. Raudales'], publisher: 'Frontiers Media SA', publicationDate: '2021-08-06', year: 2021, accessedDate: '2026-08-24', doi: '10.3389/fagro.2021.706138',
        supportedClaims: [
          "Controlled pathogenicity experiments on hemp cultivar 'Wife' confirmed that selected Pythium myriotylum and Globisporangium irregulare isolates from production substrates could reduce growth and cause chlorosis or wilt; inoculated organisms were recovered from root fragments.",
          'The source facility sampling involved coconut coir and rockwool rather than original diseased marijuana plant tissue, and Koch-style pathogenicity testing used one hemp cultivar, so the host, facility, timing, and severity cannot be generalized.',
          'Figure 7 is a whole-plant, multi-treatment composite at 14 days after inoculation that includes Pythium, Globisporangium, Fusarium, and an uninoculated control; it does not show roots or crown tissue and cannot confirm an unknown plant from appearance.',
        ],
      },
      {
        title: 'Pythium Root and Crown Rot of Hemp', organization: 'Utah State University Extension, Utah Plant Pest Diagnostic Laboratory',
        url: 'https://extension.usu.edu/planthealth/ipm/notes_ag/hemp-pythium-root-and-crown-rot', publisher: 'Utah State University Extension', accessedDate: '2026-08-24',
        supportedClaims: [
          'The institutional diagnostic note describes stunting and wilt with root rot, including loss of the root outer layer that leaves the central core, and separately describes crown infection that can girdle the stem.',
          'The note states that either root rot or crown rot can progress to rapid wilt and death and cautions that the two syndromes need not occur together, supporting separate root and crown observations.',
        ],
      },
    ],
    appendWarnings: ['Pythium species differ in temperature and production-system ecology; do not treat one environmental threshold as universal for the entire complex.'],
  },
  'fusarium-crown-root-rot': {
    sources: [
      {
        title: 'First Report of Fusarium falciforme (FSSC 3 + 4) Causing Rot of Industrial Hemp (Cannabis sativa) in California', organization: 'Plant Disease',
        url: 'https://doi.org/10.1094/PDIS-08-21-1640-PDN', publisher: 'American Phytopathological Society', publicationDate: '2022-04-21', year: 2022, accessedDate: '2026-08-17', doi: '10.1094/PDIS-08-21-1640-PDN',
        supportedClaims: ['Fusarium falciforme isolates caused internal hemp stem rot in pathogenicity work and were reisolated from inoculated stems.', 'Field root rot was associated with the same organism, but the report specifically confirmed stem-rot ability more directly than root-rot ability.'],
      },
      {
        title: 'First Report of Fusarium commune Causing Damping Off and Wilt in Cannabis sativa in Pennsylvania', organization: 'Plant Disease',
        url: 'https://doi.org/10.1094/PDIS-10-24-2067-PDN', publisher: 'American Phytopathological Society', year: 2025, accessedDate: '2026-08-17', doi: '10.1094/PDIS-10-24-2067-PDN',
        supportedClaims: ['Fusarium commune was reported from indoor Cannabis with wilted yellowing foliage, browning stems and roots, and withering, expanding the documented Fusarium species associated with Cannabis wilt/root disease.', 'The case supports maintaining a Fusarium complex label unless laboratory work resolves the causal species.'],
      },
    ],
    appendWarnings: ['The Fusarium species list on Cannabis continues to expand; a model should rank a Fusarium syndrome separately from a laboratory-confirmed species label.'],
  },
  'sclerotinia-white-mold': {
    sources: [
      {
        title: 'First Report of Sclerotinia Crown Rot Caused by Sclerotinia minor on Hemp', organization: 'Plant Disease',
        url: 'https://doi.org/10.1094/PDIS-01-19-0088-PDN', publisher: 'American Phytopathological Society', publicationDate: '2019-05-16', year: 2019, accessedDate: '2026-08-17', doi: '10.1094/PDIS-01-19-0088-PDN',
        supportedClaims: ['Sclerotinia minor caused crown rot on field-grown hemp; foliage wilted and dried while the soil-contact crown developed white-to-gray mycelium and small irregular black sclerotia.', 'The crown-centered S. minor disease overlaps white-mold syndromes but requires organism-level confirmation rather than a canopy-only label.'],
      },
    ],
    patch: {
      name: 'Sclerotinia white mold / crown rot complex', scientificName: 'Sclerotinia sclerotiorum / Sclerotinia minor',
      summary: 'A confirmed Cannabis Sclerotinia disease complex that can involve white-mold, crown-rot, wilt, and yellowing syndromes. S. sclerotiorum and S. minor are both documented on Cannabis/hemp; organism-level evidence is required because Botrytis, Fusarium, southern blight, and other molds overlap visually.',
    },
    appendWarnings: ['Sclerotinia sclerotiorum and S. minor should not be separated by canopy appearance alone; crown signs, sclerotia, culture, and molecular evidence carry more weight.'],
  },
}
