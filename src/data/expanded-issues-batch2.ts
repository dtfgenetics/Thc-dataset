import type { IssueRecord, SourceRecord } from '../types'

const source = (record: SourceRecord) => record

const sources = {
  hempSurvey: source({
    title: 'Surveying for Potential Diseases and Abiotic Disorders of Industrial Hemp (Cannabis sativa) Production',
    organization: 'Plant Health Progress',
    url: 'https://doi.org/10.1094/PHP-03-20-0017-RS',
    authors: ['Lindsey D. Thiessen', 'Tyler Schappe', 'Sarah Cochran', 'Kristin Hicks', 'Angela R. Post'],
    publisher: 'American Phytopathological Society',
    year: 2020,
    accessedDate: '2026-08-17',
    doi: '10.1094/PHP-03-20-0017-RS',
    supportedClaims: [
      'A North Carolina 2017–2018 hemp diagnostic survey identified 16 diseases caused by fungi, bacteria, oomycetes, and nematodes; the study used clinic diagnostics, morphology, sequence data for representative organisms, and pathogenicity testing for its confirmed disease set.',
      'Fusarium foliar and flower blight was common in submitted samples and involved F. equiseti and F. graminearum; flowers developed surface hyphae and light-brown necrotic tips while leaves developed circular light-brown lesions about 1 cm wide with dark margins and gray-brown aging centers.',
      'Exserohilum rostratum leaf spot occurred on leaves and stems as round brown-to-black lesions with darkened margins and abundant conidia, with ITS1/RPB2 evidence supporting the identification.',
      'Rhizoctonia solani was found on roots and crowns with plant wilting and necrotic lesions just above the soil line; pigmented septate hyphae showed characteristic right-angle branching and sequence evidence supported R. solani.',
      'Southern blight caused whole-plant wilt in reproductive hemp during hot midseason conditions, with abundant hyphae and russet-brown sclerotia on roots/lower stems and sequence/phylogenetic evidence supporting Athelia rolfsii/Sclerotium rolfsii.',
      'Meloidogyne incognita was identified from galled hemp roots with females and egg masses; affected plants had some associated stunting.',
    ],
  }),
  serratia: source({
    title: 'First Report of Serratia marcescens Causing a Leaf Spot Disease on Industrial Hemp (Cannabis sativa)',
    organization: 'Plant Disease',
    url: 'https://doi.org/10.1094/PDIS-04-19-0782-PDN',
    authors: ['T. Schappe', 'D. F. Ritchie', 'L. D. Thiessen'],
    publisher: 'American Phytopathological Society',
    publicationDate: '2020-02-10',
    year: 2020,
    accessedDate: '2026-08-17',
    doi: '10.1094/PDIS-04-19-0782-PDN',
    supportedClaims: [
      'Greenhouse-grown hemp developed small dark-brown 1–3 mm vein-limited angular lesions on leaves, stems, and flower parts; lesions coalesced into larger necrotic regions and red bacterial ooze was observed.',
      'Serratia marcescens was supported by colony/microscopic traits and 16S rRNA plus rpoB sequence evidence.',
      'Inoculated hemp developed similar lesions, controls remained symptomless, and the organism was reisolated, providing pathogenicity evidence rather than visual association alone.',
    ],
  }),
  fusariumHeadBlight: source({
    title: 'First Report of Fusarium graminearum Causing Head Blight on Hemp (Cannabis sativa) in Wisconsin',
    organization: 'Plant Disease',
    url: 'https://doi.org/10.1094/PDIS-10-25-2036-PDN',
    publisher: 'American Phytopathological Society',
    publicationDate: '2026-02-16',
    year: 2026,
    accessedDate: '2026-08-17',
    doi: '10.1094/PDIS-10-25-2036-PDN',
    supportedClaims: [
      'Fusarium graminearum was reported causing blight of hemp grain heads, strengthening evidence that Fusarium flower/head disease is a distinct Cannabis diagnostic target from Fusarium root/crown rot.',
      'The disease note used isolation and pathogen identification from symptomatic grain heads rather than relying on flower appearance alone.',
    ],
  }),
  fusariumLatent: source({
    title: 'Detection and Quantification of Latent Infection by Fusarium graminearum, Causal Agent of Fusarium Head Blight on Hemp (Cannabis sativa) Fields in Kentucky',
    organization: 'Plant Disease',
    url: 'https://doi.org/10.1094/PDIS-04-25-0774-RE',
    publisher: 'American Phytopathological Society',
    year: 2026,
    accessedDate: '2026-08-17',
    doi: '10.1094/PDIS-04-25-0774-RE',
    supportedClaims: [
      'A multi-site hemp field study used species-specific qPCR to detect and quantify F. graminearum in asymptomatic and symptomatic tissues.',
      'Latent infection occurred before visible disease and infection was more prominent during flowering, so absence of visible blight cannot exclude infection and image-only confirmation is unsafe.',
    ],
  }),
  southernBlight: source({
    title: 'First Report of Southern Blight Caused by Sclerotium rolfsii on Hemp (Cannabis sativa) in Sicily and Southern Italy',
    organization: 'Plant Disease',
    url: 'https://doi.org/10.1094/PDIS-91-5-0636A',
    publisher: 'American Phytopathological Society',
    publicationDate: '2007-04-20',
    year: 2007,
    accessedDate: '2026-08-17',
    doi: '10.1094/PDIS-91-5-0636A',
    supportedClaims: [
      'Infected hemp developed dark brown-to-tan discoloration at the soil line, crown and taproot rot, foliar yellowing, whole-plant collapse, white cottony mycelium, and tan-to-dark-brown spherical sclerotia.',
      'Pathogenicity was reproduced on hemp and Sclerotium rolfsii was reisolated while noninoculated controls remained symptomless.',
      'High summer temperatures and high soil moisture were associated with the reported outbreak but are risk context, not diagnostic proof.',
    ],
  }),
  rootKnotCompendium: source({
    title: 'Root-Knot Nematodes',
    organization: 'Compendium of Cannabis Diseases',
    url: 'https://doi.org/10.1094/9780890546284.03.05.1',
    publisher: 'American Phytopathological Society',
    publicationDate: '2022-09-13',
    year: 2022,
    accessedDate: '2026-08-17',
    doi: '10.1094/9780890546284.03.05.1',
    supportedClaims: [
      'Infection of hemp by root-knot nematodes (Meloidogyne spp.) is established, although the extent of Cannabis yield loss is not well quantified.',
      'Organism confirmation and root signs are required; above-ground stunting or chlorosis alone is nonspecific.',
    ],
  }),
}

export const expandedIssuesBatch2: IssueRecord[] = [
  {
    id: 'fungal-fusarium-foliar-flower-blight', slug: 'fusarium-foliar-flower-head-blight', name: 'Fusarium foliar, flower and head blight complex', scientificName: 'Fusarium equiseti / Fusarium graminearum', category: 'Fungal pathogen', severity: 'high', reviewStatus: 'reviewed', photoOnlyMaxConfidence: 0.4,
    summary: 'A Cannabis Fusarium disease complex affecting leaves, flowers, drying floral material, stems and grain heads. It must be separated from Fusarium root/crown rot because infection site, symptom pattern and confirmation evidence differ.',
    affectedParts: ['leaves', 'flowers', 'grain heads', 'drying floral material', 'stems'], stages: ['flower', 'reproductive', 'postharvest drying context'],
    indicators: ['Floral surfaces develop abundant hyphae with light-brown necrotic tips', 'Leaves develop roughly circular light-brown lesions with darker brown margins and gray-brown aging centers', 'Blight is centered on floral/head tissue rather than beginning as root decay', 'Fusarium macroconidia, culture, sequence or species-specific molecular evidence accompanies compatible tissue'],
    exclusions: ['Root/crown rot and vascular wilt dominate without foliar or floral lesions', 'Gray fuzzy sporulation and diagnostic evidence identify Botrytis', 'White mold and sclerotia identify a Sclerotinia or southern-blight differential', 'No Fusarium evidence is present and drying/heat/mechanical injury explains floral browning'],
    progression: [{stage:'Foliar/floral onset',description:'Localized leaf lesions or necrotic flower tips develop and surface hyphae may become visible.'},{stage:'Blight',description:'Necrosis expands through affected foliar or floral tissue.'},{stage:'Latent-infection caveat',description:'F. graminearum may be detectable before obvious blight, especially around flowering, so visual absence is not proof of absence.'}],
    lookAlikes: ['Botrytis gray mold / bud rot', 'Sclerotinia white mold', 'Alternaria leaf spot', 'Bipolaris leaf spot', 'Fusarium crown/root rot'], confirmation: ['Submit representative fresh lesion/flower tissue for culture and molecular identification when Fusarium species matters.', 'For suspected F. graminearum, species-specific molecular assays can detect infection that is not yet visually obvious.'], immediateActions: ['Separate suspect floral material from clean material and preserve diagnostic samples before treatment or disposal.', 'Inspect roots/crowns separately so root Fusarium is not conflated with foliar/flower blight.'], correctivePlan: ['Use laboratory-supported disease management and sanitation appropriate to the production stage and local crop rules.'], prevention: ['Use clean propagation/seed sources where applicable and reduce movement of symptomatic plant debris.', 'Track humidity, rainfall/leaf wetness, and flower-stage disease development without treating environment as proof of pathogen identity.'], warnings: ['Fusarium flower browning is not visually species-specific.', 'The 2020 survey identified both F. equiseti and F. graminearum in the foliar/flower blight complex; do not collapse every lesion into F. graminearum.', 'Image-only absence cannot exclude latent F. graminearum infection.'], sources: [sources.hempSurvey, sources.fusariumHeadBlight, sources.fusariumLatent], media: [],
  },
  {
    id: 'fungal-exserohilum-leaf-blight', slug: 'exserohilum-helminthosporium-leaf-blight', name: 'Exserohilum / Helminthosporium leaf blight', scientificName: 'Exserohilum rostratum (syn. Setosphaeria rostrata)', category: 'Fungal pathogen', severity: 'moderate', reviewStatus: 'reviewed', photoOnlyMaxConfidence: 0.45,
    summary: 'A confirmed outdoor hemp leaf and stem spot disease. Round brown-to-black lesions with dark margins are compatible, but abundant conidia and laboratory identification are needed because the lesion appearance overlaps other leaf spots.',
    affectedParts: ['leaves', 'stems', 'canopy'], stages: ['post-transplant', 'vegetative', 'flower', 'field production'], indicators: ['Round brown-to-black lesions develop on leaves or stems', 'Lesions have distinctly darkened margins', 'Abundant large conidia can be observed within compatible lesions', 'ITS/RPB2 or equivalent fungal identification supports Exserohilum/Setosphaeria'], exclusions: ['Pycnidia strongly support Septoria', 'Pale-centered lesions with Cercospora structures support Cercospora', 'Sooty underside masses support Pseudocercospora', 'No fungal evidence exists and chemical or mechanical injury follows an exposure pattern'], progression: [{stage:'Spot',description:'Round dark lesions appear on foliage or stems.'},{stage:'Blight',description:'Lesion burden and necrotic tissue increase and can contribute to leaf distortion or blight.'}], lookAlikes: ['Bipolaris leaf spot', 'Septoria leaf spot', 'Cercospora leaf spot', 'Alternaria leaf spot', 'Bacterial leaf spot'], confirmation: ['Examine lesion structures microscopically and use culture plus molecular identification for organism-level confirmation.', 'Photograph both surfaces and stem lesions before sampling.'], immediateActions: ['Preserve representative lesions and reduce transfer of symptomatic debris into clean areas.'], correctivePlan: ['Use confirmed leaf-blight management and sanitation appropriate to the production system.'], prevention: ['Scout field foliage and stems and reduce prolonged leaf wetness where practical.'], warnings: ['“Helminthosporium” is a historical/common disease name and does not by itself identify the modern fungal taxon.', 'Dark round spots are not Exserohilum-specific.'], sources: [sources.hempSurvey], media: [],
  },
  {
    id: 'bacterial-serratia-leaf-spot', slug: 'serratia-marcescens-leaf-spot', name: 'Serratia bacterial leaf spot', scientificName: 'Serratia marcescens', category: 'Bacterial pathogen', severity: 'high', reviewStatus: 'reviewed', photoOnlyMaxConfidence: 0.5,
    summary: 'A pathogenicity-confirmed Cannabis bacterial disease producing small vein-limited angular lesions that can coalesce across leaves, stems and flower parts. Red bacterial ooze is useful supporting evidence but species confirmation requires laboratory identification.', affectedParts: ['leaves', 'stems', 'flower parts'], stages: ['seedling', 'vegetative', 'flower', 'greenhouse production'], indicators: ['Small dark-brown 1–3 mm lesions are angular or vein-limited', 'Lesions coalesce into larger necrotic regions as disease advances', 'Red bacterial ooze streams from affected plant tissue', 'Laboratory culture and 16S/rpoB or equivalent evidence supports Serratia marcescens'], exclusions: ['No bacterial ooze or lab evidence exists and lesions fit a fungal leaf spot better', 'Xanthomonas or another bacterial pathogen is identified', 'Chemical/contact injury follows a spray or exposure boundary'], progression: [{stage:'Early',description:'Small dark vein-limited lesions develop.'},{stage:'Coalescing',description:'Lesions merge into larger necrotic regions on leaves and other aerial tissues.'},{stage:'Severe',description:'Large tissue areas can be lost and whole plants were lost in the original production observations.'}], lookAlikes: ['Xanthomonas bacterial leaf spot', 'Septoria leaf spot', 'Cercospora leaf spot', 'Anthracnose', 'Contact spray injury'], confirmation: ['Collect fresh lesion-margin tissue for bacterial isolation and molecular identification.', 'Treat red ooze as a strong clue, not a substitute for organism confirmation.'], immediateActions: ['Separate strongly affected propagation material and avoid moving wet symptomatic tissue through clean areas.', 'Preserve a fresh sample before sanitation.'], correctivePlan: ['Use laboratory-confirmed bacterial-disease sanitation and management appropriate to the production system.'], prevention: ['Sanitize tools/contact surfaces and minimize splash movement from symptomatic plants.', 'Use clean propagation material.'], warnings: ['Serratia includes strains of human-health relevance; use appropriate hygiene and diagnostic-lab handling.', 'Angular necrotic lesions alone are not Serratia-specific.'], sources: [sources.serratia], media: [],
  },
  {
    id: 'fungal-southern-blight', slug: 'southern-blight-athelia-rolfsii', name: 'Southern blight', scientificName: 'Athelia rolfsii (Sclerotium rolfsii)', category: 'Root pathogen', severity: 'critical', reviewStatus: 'reviewed', photoOnlyMaxConfidence: 0.55,
    summary: 'A warm-condition soilborne Cannabis disease centered at the soil line, crown and taproot. White cottony mycelium plus tan-to-brown spherical sclerotia at the plant base are strong signs, but wilt alone is nonspecific.', affectedParts: ['lower stem at soil line', 'crown', 'taproot', 'root surface', 'whole plant'], stages: ['vegetative', 'reproductive', 'warm field conditions'], indicators: ['Dark brown-to-tan discoloration develops near the soil line', 'Rot extends into crown or taproot while foliage yellows and the plant wilts/collapses', 'White cottony mycelium develops on basal tissue or adjacent soil', 'Numerous spherical tan-to-dark-brown sclerotia occur with compatible basal rot'], exclusions: ['No basal rot, mycelium or sclerotia are present and measured drought explains wilt', 'Laboratory evidence identifies Rhizoctonia, Fusarium, Pythium or another root/crown pathogen', 'White growth is confined to leaves/flowers without basal disease'], progression: [{stage:'Basal lesion',description:'Dark tan-brown discoloration appears at the soil line.'},{stage:'Crown/root rot',description:'Rot moves into crown and taproot as foliage yellows.'},{stage:'Collapse',description:'Whole plants can wilt and collapse while white mycelium and brown sclerotia accumulate at the base.'}], lookAlikes: ['Rhizoctonia root rot / sore shin', 'Fusarium crown/root rot', 'Pythium root rot', 'Sclerotinia white mold', 'Severe root-zone hypoxia'], confirmation: ['Inspect the soil line/crown/root surface for characteristic mycelium and sclerotia and submit tissue/culture for organism confirmation.', 'Record temperature/moisture context, but do not use hot wet conditions as diagnostic proof.'], immediateActions: ['Isolate affected root-zone material and prevent movement of contaminated soil or debris to clean areas.', 'Preserve basal tissue and sclerotia for diagnostic testing.'], correctivePlan: ['Use confirmed soilborne-disease sanitation and crop-legal management appropriate to the setting.', 'Address excess moisture where measured without assuming moisture correction eliminates established pathogen inoculum.'], prevention: ['Avoid moving contaminated soil or plant debris between production areas.', 'Monitor crown/root health during warm wet periods.'], warnings: ['Whole-plant wilt alone cannot identify southern blight.', 'Sclerotia and laboratory evidence are substantially stronger than canopy appearance.'], sources: [sources.hempSurvey, sources.southernBlight], media: [],
  },
  {
    id: 'root-rhizoctonia', slug: 'rhizoctonia-sore-shin-root-rot', name: 'Rhizoctonia sore shin / root and crown rot', scientificName: 'Rhizoctonia solani', category: 'Root pathogen', severity: 'high', reviewStatus: 'reviewed', photoOnlyMaxConfidence: 0.45,
    summary: 'A Cannabis root/crown disease documented as wilting with necrotic lesions at the plant base just above the soil line. Characteristic right-angle branching hyphae and laboratory identification are needed because the canopy response overlaps other root diseases.', affectedParts: ['roots', 'crown', 'lower stem just above soil line', 'whole plant'], stages: ['seedling', 'transplant', 'vegetative', 'reproductive'], indicators: ['Plants wilt while necrotic lesions develop at the stem base near the soil line', 'Roots/crown show compatible necrotic disease', 'Pigmented septate hyphae from lesions branch at roughly 90 degrees with basal constriction', 'ITS/18S or other laboratory evidence supports Rhizoctonia solani'], exclusions: ['White cottony basal mycelium with round brown sclerotia strongly supports southern blight', 'Soft/slimy roots and oomycete evidence support Pythium', 'Vascular discoloration and Fusarium evidence support Fusarium wilt/crown disease', 'No basal/root lesions exist and water-status measurements explain wilt'], progression: [{stage:'Basal infection',description:'Necrotic lesions develop around crown/lower stem or roots.'},{stage:'Root/crown impairment',description:'Root function declines and above-ground wilt becomes more evident.'}], lookAlikes: ['Southern blight', 'Pythium root rot', 'Fusarium crown/root rot', 'Root binding', 'Drought / water-deficit stress'], confirmation: ['Inspect and photograph roots/crown and lower-stem lesions; submit lesion tissue for fungal morphology and molecular identification.', 'Do not confirm Rhizoctonia from wilted foliage alone.'], immediateActions: ['Separate suspect root-zone material and preserve a fresh lesion sample.', 'Check irrigation/moisture and root binding concurrently.'], correctivePlan: ['Use confirmed root-disease sanitation and crop-appropriate management.', 'Correct measured root-zone stressors that may worsen disease.'], prevention: ['Use clean media/containers and avoid moving contaminated soil.', 'Inspect transplants for crown lesions and bound/diseased roots.'], warnings: ['Rhizoctonia can coexist with other root stresses/pathogens.', 'Canopy wilt is not organism-specific.'], sources: [sources.hempSurvey], media: [],
  },
  {
    id: 'nematode-root-knot', slug: 'root-knot-nematodes', name: 'Root-knot nematodes', scientificName: 'Meloidogyne spp. (including M. incognita)', category: 'Nematode', severity: 'moderate', reviewStatus: 'reviewed', photoOnlyMaxConfidence: 0.55,
    summary: 'A confirmed Cannabis root-parasitic nematode problem. Root galling with females/egg masses is far more discriminating than above-ground stunting or chlorosis, which overlap nearly every root-zone disorder.', affectedParts: ['roots', 'root galls', 'whole plant secondarily'], stages: ['vegetative', 'flower', 'field production'], indicators: ['Roots develop characteristic localized galls or knots', 'Females can be present inside galled root tissue with egg masses associated with roots', 'Plants may be stunted or chlorotic secondarily', 'Nematode morphology or molecular testing identifies Meloidogyne'], exclusions: ['Root enlargements are normal lateral-root structures rather than galls', 'No galls/nematodes are found and a different root disease or abiotic condition is confirmed', 'Only canopy stunting/chlorosis is available without root inspection'], progression: [{stage:'Root infection',description:'Nematodes establish feeding sites and root galls develop.'},{stage:'Increasing burden',description:'Gall number and root disruption increase; above-ground growth may become stunted or chlorotic.'}], lookAlikes: ['Rhizoctonia root rot', 'Fusarium root/crown disease', 'Root binding', 'Nutrient deficiency', 'Drought / water-deficit stress'], confirmation: ['Wash and inspect the complete root system for true galls and collect roots/soil for nematode analysis.', 'Use adult/juvenile morphology and/or validated molecular assays when Meloidogyne species matters.'], immediateActions: ['Prevent movement of potentially infested soil/root debris into clean production areas.', 'Preserve representative galled roots and surrounding soil for diagnosis.'], correctivePlan: ['Base management on confirmed nematode identification, production system, and locally legal options.'], prevention: ['Use clean planting material/media and avoid moving infested soil on tools/equipment.', 'Inspect roots when unexplained stunting occurs in field/container production.'], warnings: ['Above-ground chlorosis and stunting are nonspecific and should have very low diagnostic weight without root evidence.', 'Cannabis yield-loss thresholds for root-knot nematodes remain incompletely defined.'], sources: [sources.hempSurvey, sources.rootKnotCompendium], media: [],
  },
]
