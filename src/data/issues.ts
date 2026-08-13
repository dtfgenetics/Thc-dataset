import type { IssueRecord, SourceRecord } from '../types'

const sources: Record<string, SourceRecord> = {
  msuNutrients: {
    title: 'Characterization of Nutrient Disorders of Cannabis sativa',
    organization: 'Applied Sciences (Cockson et al.)',
    url: 'https://www.mdpi.com/2076-3417/9/20/4432',
    year: 2019,
    accessedDate: '2026-08-13',
    supportedClaims: ['Cannabis nutrient disorders produce repeatable symptom-location and progression patterns that must be interpreted with plant age and tissue position.'],
  },
  cornellPm: {
    title: 'First Report of Powdery Mildew Caused by Golovinomyces ambrosiae on Cannabis sativa in North America',
    organization: 'Plant Disease (Pépin et al.)',
    url: 'https://apsjournals.apsnet.org/doi/10.1094/PDIS-01-19-0049-PDN',
    year: 2019,
    accessedDate: '2026-08-13',
    supportedClaims: ['Golovinomyces ambrosiae causes powdery mildew on Cannabis sativa and produces superficial white colonies on susceptible tissue.'],
  },
  ucMites: {
    title: 'Spider Mites',
    organization: 'University of California Statewide IPM Program',
    url: 'https://ipm.ucanr.edu/home-and-landscape/spider-mites/',
    accessedDate: '2026-08-13',
    supportedClaims: ['Spider-mite feeding causes stippling and established populations can produce webbing; leaf-underside inspection is required.'],
  },
  hpLv: {
    title: 'Hop Latent Viroid: A Hidden Threat to the Cannabis Industry',
    organization: 'Viruses (Adkar-Purushothama et al.)',
    url: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC10053334/',
    year: 2023,
    accessedDate: '2026-08-13',
    supportedClaims: ['Hop latent viroid can be asymptomatic or associated with reduced vigor, shortened internodes, brittle growth, poor rooting, and reduced yield or quality; molecular testing is needed for confirmation.'],
  },
  pythium: {
    title: 'Several Pythium species cause crown and root rot on cannabis plants grown under commercial greenhouse conditions',
    organization: 'Canadian Journal of Plant Pathology (Punja et al.)',
    url: 'https://www.tandfonline.com/doi/full/10.1080/07060661.2021.1954695',
    year: 2022,
    accessedDate: '2026-08-13',
    supportedClaims: ['Multiple Pythium species cause crown and root rot in greenhouse cannabis, and pathogen identity cannot be resolved reliably from above-ground symptoms alone.'],
  },
  usuRussetMite: {
    title: 'Hemp Russet Mite',
    organization: 'Utah State University Extension, Utah Plant Pest Diagnostic Laboratory',
    url: 'https://extension.usu.edu/planthealth/ipm/notes_ag/hemp-hemp-russet-mite-',
    publisher: 'Utah State University Extension',
    accessedDate: '2026-08-13',
    supportedClaims: [
      'Hemp russet mites are microscopic, cigar-shaped eriophyid mites usually found on leaf undersides and best identified with high magnification.',
      'High populations can cause fine spotting, bronzing, reduced leaf size, brittle foliage, upward edge curl, and stem bronzing.',
      'Spider mites, thrips, and physiological leaf curl or yellowing are documented look-alikes.',
    ],
  },
  ncsuRussetMite: {
    title: 'Hemp Russet Mite in Industrial Hemp',
    organization: 'NC State Extension',
    url: 'https://content.ces.ncsu.edu/hemp-russet-mite-in-industrial-hemp',
    authors: ['Melissa Pulkoski', 'Hannah Burrack'],
    publisher: 'North Carolina State University Extension',
    publicationDate: '2020-08-04',
    accessedDate: '2026-08-13',
    supportedClaims: [
      'The absence of webbing helps distinguish hemp russet mite from spider mites, but microscopy is necessary because injury resembles disease and abiotic stress.',
      'Stem, petiole, and leaf feeding can cause stunting, smaller leaves, dull gray or bronzed tissue, and suppressed or dwarfed buds.',
      'The two referenced photographs are credited to Whitney Cranshaw, Colorado State University, Bugwood.org, under CC BY 4.0.',
    ],
  },
  russetMiteCounts: {
    title: 'Novel Approach to Tally Aculops cannabicola (Acari: Eriophyidae) Using Photographs of Hemp Leaves',
    organization: 'Journal of Economic Entomology (Falcon-Brindis et al.)',
    url: 'https://doi.org/10.1093/jee/toad004',
    authors: ['A. Falcon-Brindis', 'C. L. Bradley'],
    publisher: 'Oxford University Press for the Entomological Society of America',
    publicationDate: '2023-01-23',
    year: 2023,
    accessedDate: '2026-08-13',
    doi: '10.1093/jee/toad004',
    supportedClaims: [
      'Hemp russet mites are approximately 160–210 micrometres long and are easily missed with standard low-power hand lenses.',
      'Image-based counts require microscope photographs of multiple leaflet sections; ordinary whole-plant photographs cannot confirm the pest.',
      'Feeding is associated with chlorosis, stunting, brittle leaf breakage, and reduced flower-bud size or resin production at high populations.',
    ],
  },
}

const issue = (record: IssueRecord): IssueRecord => record

export const issues: IssueRecord[] = [
  issue({
    id: 'nut-def-n', slug: 'nitrogen-deficiency', name: 'Nitrogen deficiency', category: 'Nutrient deficiency', severity: 'moderate', reviewStatus: 'reviewed',
    summary: 'A mobile-nutrient shortage that usually begins as an even yellowing of older leaves before moving upward.',
    affectedParts: ['older leaves', 'whole plant'], stages: ['vegetative', 'flower'],
    indicators: ['Older leaves yellow first', 'Whole plant pale', 'Lower leaves drop', 'Growth slows'],
    exclusions: ['New growth is affected first', 'Yellowing is sharply interveinal', 'Root-zone EC is already high'],
    progression: [{stage:'Early',description:'Lower leaves lose uniform green color.'},{stage:'Moderate',description:'Yellowing advances upward and older leaves drop.'},{stage:'Advanced',description:'Canopy thins and growth or flower development slows.'}],
    lookAlikes: ['Normal late-flower fade','Overwatering or root hypoxia','Magnesium deficiency'],
    confirmation: ['Check whether symptoms begin on the oldest leaves.','Review root-zone pH and EC before adding fertilizer.'],
    immediateActions: ['Measure pH and EC/PPM before changing feed.','Correct watering or root-zone problems first.'],
    correctivePlan: ['If EC is low and pH is in range, increase complete nutrition gradually.','Recheck new growth over 5–7 days.'],
    prevention: ['Track input and runoff EC.','Avoid reducing nitrogen too early in flower.'], warnings: ['Do not diagnose from one yellow leaf.','Do not add nitrogen when high EC or root damage is the primary cause.'],
    sources: [sources.msuNutrients], media: [],
  }),
  issue({
    id: 'nut-def-mg', slug: 'magnesium-deficiency', name: 'Magnesium deficiency', category: 'Nutrient deficiency', severity: 'moderate', reviewStatus: 'reviewed',
    summary: 'Interveinal chlorosis on older leaves that can advance into rust-colored spotting while veins remain greener.',
    affectedParts: ['older leaves'], stages: ['vegetative', 'flower'],
    indicators: ['Older leaves yellow between green veins', 'Rust or tan spotting', 'Leaf edges may curl upward'],
    exclusions: ['Newest leaves are the only tissue affected', 'Uniform yellowing without green veins', 'White surface growth wipes away'],
    progression: [{stage:'Early',description:'Pale tissue develops between veins on lower leaves.'},{stage:'Moderate',description:'Interveinal yellowing becomes pronounced and rust spots appear.'},{stage:'Advanced',description:'Affected tissue becomes necrotic and leaves drop.'}],
    lookAlikes: ['Potassium deficiency','Iron deficiency','High-EC root stress'], confirmation: ['Confirm symptom position on the plant.','Check pH and magnesium balance rather than treating from color alone.'],
    immediateActions: ['Verify root-zone pH and EC.','Review calcium-to-magnesium balance and water source.'], correctivePlan: ['Correct pH or excess salts first.','Adjust magnesium only when the measured context supports it.'], prevention: ['Record source-water mineral content.','Use balanced nutrition and avoid repeated blind supplementation.'], warnings: ['Existing damaged leaves may not recover.','Excess magnesium can contribute to calcium imbalance.'], sources: [sources.msuNutrients], media: [],
  }),
  issue({
    id: 'nut-def-k', slug: 'potassium-deficiency', name: 'Potassium deficiency', category: 'Nutrient deficiency', severity: 'high', reviewStatus: 'reviewed',
    summary: 'Marginal scorch and rusty spotting that often begins on older leaves and worsens during fast growth or flowering.',
    affectedParts: ['older leaves', 'leaf margins'], stages: ['vegetative', 'flower'], indicators: ['Burned leaf edges', 'Rust or tan spotting', 'Weak stems', 'Older leaves affected first'], exclusions: ['Only the tips are burned after feeding', 'Damage is limited to the light-facing canopy', 'White powder or webbing is visible'], progression: [{stage:'Early',description:'Leaf margins pale and small rust spots form.'},{stage:'Moderate',description:'Edges brown and curl while spotting spreads inward.'},{stage:'Advanced',description:'Leaves become crisp and plant vigor declines.'}], lookAlikes: ['Nutrient burn or salt buildup','Heat or light stress','Magnesium deficiency'], confirmation: ['Compare margin pattern with measured EC and pH.','Check whether the damage begins on older tissue.'], immediateActions: ['Measure root-zone EC and pH.','Rule out salt buildup before increasing potassium.'], correctivePlan: ['Restore balanced nutrition after correcting root-zone conditions.'], prevention: ['Avoid extreme bloom-booster ratios.','Monitor dryback and EC accumulation.'], warnings: ['Adding potassium to high-EC media can worsen the injury.'], sources: [sources.msuNutrients], media: [],
  }),
  issue({
    id: 'nut-tox-n', slug: 'nitrogen-toxicity', name: 'Nitrogen toxicity', category: 'Nutrient toxicity', severity: 'moderate', reviewStatus: 'reviewed', summary: 'Excess nitrogen produces unusually dark foliage, downward clawing, soft growth, and delayed reproductive behavior.', affectedParts: ['leaves','stems'], stages: ['vegetative','flower'], indicators: ['Dark clawed leaves','Very dark green foliage','Soft weak stems','Burned leaf tips'], exclusions: ['Leaves are pale overall','Clawing appears only during severe drought','No recent high-nitrogen input'], progression: [{stage:'Early',description:'Foliage becomes unusually dark and glossy.'},{stage:'Moderate',description:'Tips curl downward and soft growth accumulates.'},{stage:'Advanced',description:'Tip burn, weak stems, and delayed flowering occur.'}], lookAlikes: ['Overwatering or root hypoxia','Broad mite injury','Nutrient burn or salt buildup'], confirmation: ['Review fertilizer analysis and root-zone EC.'], immediateActions: ['Stop nitrogen-heavy additives.','Measure EC before flushing or changing feed.'], correctivePlan: ['Return to a balanced stage-appropriate program.'], prevention: ['Avoid stacking multiple nitrogen sources.'], warnings: ['Do not flush automatically without measuring salinity and drainage.'], sources: [sources.msuNutrients], media: [],
  }),
  issue({
    id: 'mite-spider', slug: 'two-spotted-spider-mites', name: 'Two-spotted spider mites', scientificName: 'Tetranychus urticae', category: 'Mite', severity: 'high', reviewStatus: 'reviewed', summary: 'Sap-feeding mites cause fine stippling from the leaf underside and visible webbing as populations increase.', affectedParts: ['leaf underside','canopy','flower'], stages: ['all'], indicators: ['Tiny yellow or white stipples','Fine webbing','Visible mites or eggs under magnification'], exclusions: ['Silver scraped streaks with black specks','No organisms after careful underside inspection','Damage follows a nutrient-mobility pattern'], progression: [{stage:'Early',description:'Fine pale stippling appears on individual leaves.'},{stage:'Moderate',description:'Bronzing spreads and mites or eggs are visible below.'},{stage:'Advanced',description:'Webbing spans leaves or flowers and plants decline.'}], lookAlikes: ['Thrips','Hemp russet mites','Spray residue'], confirmation: ['Inspect undersides with 30–60× magnification.','Look for round eggs and moving mites.'], immediateActions: ['Isolate affected plants.','Inspect nearby plants and remove heavily infested material safely.'], correctivePlan: ['Use a legal crop- and stage-appropriate IPM rotation.','Repeat monitoring between treatments.'], prevention: ['Quarantine incoming plants.','Scout leaf undersides weekly.'], warnings: ['Avoid spraying unsuitable products on flowers.','Webbing indicates an established population, not an early case.'], sources: [sources.ucMites], media: [],
  }),
  issue({
    id: 'mite-hemp-russet', slug: 'hemp-russet-mite', name: 'Hemp russet mite', scientificName: 'Aculops cannabicola', category: 'Mite', severity: 'high', reviewStatus: 'reviewed',
    summary: 'A microscopic eriophyid mite whose feeding can cause localized bronzing, brittle or reduced leaves, distorted edges, stunting, and suppressed floral growth without the webbing typical of spider mites.',
    affectedParts: ['young leaves', 'leaf undersides', 'petioles', 'stems', 'growing tips', 'flower buds'], stages: ['vegetative', 'pre-flower', 'flower'],
    indicators: ['Dull gray or bronzed foliage', 'Brittle or reduced leaf size', 'Leaf edges curl upward or downward', 'Stem or petiole bronzing', 'Stunted growing tips', 'No webbing despite mite-like damage'],
    exclusions: ['Fine webbing and round spider-mite eggs are present', 'Only interveinal chlorosis follows an older-leaf nutrient pattern', 'Damage is restricted to the hottest or brightest canopy surface', 'No cigar-shaped mites are found after adequate microscope sampling'],
    progression: [
      {stage:'Low population',description:'Visible injury may be absent; mites occupy protected sites around veins, trichomes, petioles, and leaf undersides.'},
      {stage:'Developing injury',description:'Fine spotting, dull gray-green tissue, bronzing, edge curl, and reduced or brittle leaves become apparent on affected shoots.'},
      {stage:'High population',description:'Stunting, stem bronzing, deformed growing tips, and reduced or dwarfed flower buds can develop; dense mites or cast skins may resemble tan powder.'},
    ],
    lookAlikes: ['Two-spotted spider mites', 'Thrips', 'Broad mites', 'Heat or light stress', 'Nutrient or root-zone stress', 'Powdery residue'],
    confirmation: [
      'Sample both symptomatic and adjacent apparently healthy leaves; inspect undersides, midribs, petioles, and protected trichome zones with a dissecting or digital microscope.',
      'Confirm pale, cigar-shaped eriophyid mites with only two pairs of legs; ordinary phone or whole-plant images are not sufficient.',
      'For repeatable image counts, photograph multiple leaflet sections under microscope magnification rather than relying on a single field of view.',
    ],
    immediateActions: ['Quarantine suspect plants and stop moving cuttings, tools, clothing, or plant debris into clean areas.', 'Inspect nearby plants under adequate magnification before choosing a treatment.'],
    correctivePlan: ['Use only controls legal for the crop, jurisdiction, and growth stage, following the current product label.', 'Track mite counts on fixed leaf positions after intervention; visible injury can lag behind population change.', 'Remove severely infested material without spreading mites and clean shared tools between plants.'],
    prevention: ['Start with inspected, mite-free propagation material.', 'Quarantine and microscope-screen incoming clones.', 'Maintain routine microscope scouting because low populations can be visually silent.'],
    warnings: ['Leaf curl or bronzing alone is not diagnostic.', 'Do not confuse tan cast-skin accumulations with fungal powder.', 'A compatible CC BY license permits reuse with attribution, but these reference images remain excluded from model training until file hashes, duplicate checks, and a separate training review are completed.'],
    sources: [sources.usuRussetMite, sources.ncsuRussetMite, sources.russetMiteCounts],
    media: [
      {
        id: 'ncsu-hrm-life-stages-5574608',
        url: 'https://content.ces.ncsu.edu/media/images/5574608-WEB.jpeg',
        thumbnailUrl: 'https://content.ces.ncsu.edu/media/images/5574608-WEB.jpeg',
        alt: 'Pale hemp russet mites on the surface of a hemp leaf under magnification',
        caption: 'Multiple life stages of hemp russet mite on hemp leaf tissue; use as a morphology reference, not as proof from an ordinary plant photograph.',
        creator: 'Whitney Cranshaw, Colorado State University, Bugwood.org',
        license: 'CC BY 4.0',
        sourceUrl: 'https://content.ces.ncsu.edu/print_image/12580',
        mediaType: 'image',
        requiredAttribution: 'Whitney Cranshaw, Colorado State University, Bugwood.org; CC BY 4.0',
        diagnosticLabel: 'hemp-russet-mite-microscope-life-stages',
        reviewStatus: 'approved-reference',
        trainingPermission: 'permitted',
        sha256: '2b663263afccc22aa652e5968e0f7f3932f1b6fb0077fb42784ccd811b1b2d35',
        width: 384, height: 257,
        view: 'microscope',
        stage: 'multiple mite life stages', severity: 'confirmed presence', confirmation: 'expert-reviewed', trainingEligible: false,
      },
      {
        id: 'ncsu-hrm-canopy-damage-5574606',
        url: 'https://content.ces.ncsu.edu/media/images/5574606-WEB.jpeg',
        thumbnailUrl: 'https://content.ces.ncsu.edu/media/images/5574606-WEB.jpeg',
        alt: 'Top of a hemp plant showing yellowing, stunting, and distorted growth associated with hemp russet mite injury',
        caption: 'Canopy-level hemp russet mite damage showing yellowing and stunting; microscopy is still required because this appearance overlaps abiotic and disease injury.',
        creator: 'Whitney Cranshaw, Colorado State University, Bugwood.org',
        license: 'CC BY 4.0',
        sourceUrl: 'https://content.ces.ncsu.edu/print_image/12579',
        mediaType: 'image',
        requiredAttribution: 'Whitney Cranshaw, Colorado State University, Bugwood.org; CC BY 4.0',
        diagnosticLabel: 'hemp-russet-mite-whole-plant-damage',
        reviewStatus: 'approved-reference',
        trainingPermission: 'permitted',
        sha256: '3bb67e69f4bf90404b4581c62d806f6523f663fbd0ab6ca8cce5abb99d4fe6f6',
        width: 384, height: 288,
        view: 'whole-plant',
        stage: 'pre-harvest or harvest', severity: 'symptomatic', confirmation: 'expert-reviewed', trainingEligible: false,
      },
    ],
  }),
  issue({
    id: 'insect-thrips', slug: 'thrips', name: 'Thrips', category: 'Insect', severity: 'moderate', reviewStatus: 'provisional', summary: 'Thrips scrape surface cells, leaving silvery scars, small black fecal specks, and distorted new tissue in severe cases.', affectedParts: ['leaves','new growth'], stages: ['all'], indicators: ['Silver scraped streaks','Small black specks','Tiny slender insects'], exclusions: ['Fine webbing is present','Damage is uniform between veins','Circular lesions have defined halos'], progression: [{stage:'Early',description:'Short silvery scars appear on leaves.'},{stage:'Moderate',description:'Scarring and black specks become widespread.'},{stage:'Advanced',description:'New growth distorts and vigor drops.'}], lookAlikes: ['Spider mites','Foliar spray residue','Wind abrasion'], confirmation: ['Tap foliage over white paper.','Use sticky cards and a hand lens to confirm slender insects.'], immediateActions: ['Isolate affected plants and inspect the full crop.'], correctivePlan: ['Use a legal stage-appropriate IPM rotation and verify control with monitoring.'], prevention: ['Screen intake air where practical.','Inspect incoming plants and media.'], warnings: ['Do not identify thrips from silver damage alone.'], sources: [sources.ucMites], media: [],
  }),
  issue({
    id: 'fungal-pm', slug: 'powdery-mildew', name: 'Powdery mildew', category: 'Fungal pathogen', severity: 'high', reviewStatus: 'reviewed', summary: 'A white superficial fungal growth that forms expanding powdery colonies on leaves, stems, petioles, and reproductive tissue.', affectedParts: ['leaf surface','stem','flower'], stages: ['all'], indicators: ['White powder on leaves','Patches expand across surfaces','Powder can transfer when touched'], exclusions: ['Residue follows droplet outlines after spraying','Webbing or insects are visible','The pale area is inside the tissue and cannot be disturbed'], progression: [{stage:'Early',description:'Small white circular colonies appear.'},{stage:'Moderate',description:'Colonies merge across leaves and stems.'},{stage:'Advanced',description:'Tissue yellows or dies and reproductive material may be contaminated.'}], lookAlikes: ['Foliar spray residue','Mineral deposits','Trichomes on floral tissue'], confirmation: ['Inspect colony margins with magnification.','Use a plant diagnostic lab when legal or commercial decisions depend on certainty.'], immediateActions: ['Isolate affected material and reduce spore movement.','Stop overhead wetting and review humidity/airflow.'], correctivePlan: ['Use legal stage-appropriate controls and sanitation.','Remove heavily affected tissue without dispersing spores.'], prevention: ['Maintain clean intake material and stable humidity.','Inspect dense interior canopy zones.'], warnings: ['Do not consume visibly mold-contaminated material.','Do not assume every white mark is mildew.'], sources: [sources.cornellPm], media: [],
  }),
  issue({
    id: 'root-pythium', slug: 'pythium-root-rot', name: 'Pythium root rot', scientificName: 'Pythium spp.', category: 'Root pathogen', severity: 'critical', reviewStatus: 'reviewed', summary: 'An oomycete root disease favored by wet, low-oxygen conditions; affected roots discolor, soften, and lose function.', affectedParts: ['roots','crown','whole plant'], stages: ['all'], indicators: ['Brown slimy roots','Wilting despite moisture','Stunting and yellowing','Crown rot in severe cases'], exclusions: ['Roots are tan from media staining but firm','Container is very light and dry','Only one leaf shows damage'], progression: [{stage:'Early',description:'Root tips lose white color and growth slows.'},{stage:'Moderate',description:'Roots brown and soften while foliage wilts or yellows.'},{stage:'Advanced',description:'Root systems collapse and crown tissue may rot.'}], lookAlikes: ['Overwatering or root hypoxia','Phytophthora root rot','Fusarium crown disease'], confirmation: ['Inspect cleaned roots for texture and active white tips.','Laboratory testing is required to distinguish similar root pathogens.'], immediateActions: ['Isolate affected root-zone water and tools.','Restore oxygenation and correct saturation.'], correctivePlan: ['Remove irrecoverable plants where appropriate and sanitize wetted equipment.','Use only legal crop-appropriate treatments.'], prevention: ['Control water temperature, sanitation, oxygen, and irrigation duration.'], warnings: ['Visual symptoms cannot reliably identify Pythium to species.'], sources: [sources.pythium], media: [],
  }),
  issue({
    id: 'viroid-hplvd', slug: 'hop-latent-viroid', name: 'Hop latent viroid', scientificName: 'Hop latent viroid (HLVd)', category: 'Viroid', severity: 'critical', reviewStatus: 'reviewed', summary: 'A systemic viroid that may remain asymptomatic or produce stunting, brittle stems, short internodes, weak rooting, and reduced reproductive performance.', affectedParts: ['whole plant','stem','roots','flower'], stages: ['all'], indicators: ['Short internodes','Brittle stems or leaves','Stunted growth','Weak flower production'], exclusions: ['Symptoms resolve after correcting a measured root-zone problem','One branch alone is mechanically damaged','No comparison with a healthy clone exists'], progression: [{stage:'Latent',description:'Plant may show no reliable visual symptoms.'},{stage:'Expression',description:'Reduced vigor, short internodes, brittle growth, or poor rooting develops.'},{stage:'Advanced',description:'Yield and quality decline; secondary stress may intensify.'}], lookAlikes: ['Genetic dwarfism','Root disease','Chronic environmental stress'], confirmation: ['Use a validated RT-PCR or equivalent laboratory test.','Retest representative tissue when timing or sampling may affect detection.'], immediateActions: ['Quarantine suspect plants and stop sharing tools or propagation material.'], correctivePlan: ['Base culling and sanitation decisions on validated testing and facility protocol.'], prevention: ['Test mother stock and incoming clones.','Disinfect tools between plants with a validated viroid protocol.'], warnings: ['HLVd cannot be confirmed from a photograph.','Do not label a plant infected without laboratory evidence.'], sources: [sources.hpLv], media: [],
  }),
  issue({
    id: 'gen-variegation', slug: 'genetic-variegation', name: 'Genetic variegation or chimera', category: 'Genetic / developmental', severity: 'low', reviewStatus: 'provisional', summary: 'Stable sectoring or repeating pale tissue can be genetic or chimeric, especially when it remains localized without spreading or reducing vigor.', affectedParts: ['leaf','branch'], stages: ['all'], indicators: ['Sharp pale or yellow sectors','Pattern repeats on one branch','Plant remains otherwise vigorous'], exclusions: ['Mosaic pattern spreads across new shoots','Leaf distortion and stunting progress','Pest or chemical exposure is present'], progression: [{stage:'Stable',description:'Pattern repeats predictably as the affected meristem grows.'}], lookAlikes: ['Mosaic virus complex','Micronutrient deficiency','Herbicide injury'], confirmation: ['Compare successive leaves and branches.','Use laboratory pathogen testing if mosaic disease remains plausible.'], immediateActions: ['Quarantine if infectious disease cannot be excluded.'], correctivePlan: ['Document progression before making irreversible decisions.'], prevention: ['Keep clean propagation records and healthy comparators.'], warnings: ['A photograph cannot exclude virus or viroid infection.'], sources: [], media: [],
  }),
  issue({
    id: 'env-heat', slug: 'heat-light-stress', name: 'Heat or light stress', category: 'Environmental stress', severity: 'moderate', reviewStatus: 'provisional', summary: 'Excess radiation, leaf temperature, or vapor demand causes upper-canopy cupping, bleaching, edge damage, and accelerated dryback.', affectedParts: ['upper canopy','leaf margins'], stages: ['all'], indicators: ['Edges curl upward','Leaf tacoing or cupping','Bleached tops','Damage is strongest near the light'], exclusions: ['Symptoms begin on shaded lower leaves','Webbing, pests, or colonies are present','Root-zone measurements explain the pattern better'], progression: [{stage:'Early',description:'Upper leaves angle or cup away from the stress.'},{stage:'Moderate',description:'Margins dry and tissue pales near the light.'},{stage:'Advanced',description:'Bleaching and necrosis reduce canopy function.'}], lookAlikes: ['Potassium deficiency','Windburn','Drought stress'], confirmation: ['Measure canopy PPFD, leaf temperature, air temperature, and humidity.'], immediateActions: ['Reduce acute heat or light load without making extreme changes.','Verify irrigation timing and air movement.'], correctivePlan: ['Bring environmental targets back gradually and monitor new growth.'], prevention: ['Map canopy light and measure at plant height.'], warnings: ['Do not diagnose from leaf angle alone.'], sources: [], media: [],
  }),
  issue({
    id: 'water-over', slug: 'overwatering-root-hypoxia', name: 'Overwatering or root hypoxia', category: 'Water / root-zone', severity: 'high', reviewStatus: 'provisional', summary: 'Persistently saturated media limits oxygen at the roots, causing droop, slow growth, chlorosis, and increased root-disease risk.', affectedParts: ['roots','whole plant'], stages: ['all'], indicators: ['Droops while wet','Slow growth','Pale foliage','Media remains wet too long'], exclusions: ['Container is light and dry','Roots are actively white and media dries normally','Wilt is limited to one damaged branch'], progression: [{stage:'Early',description:'Leaves droop while the root zone remains wet.'},{stage:'Moderate',description:'Growth slows and older foliage yellows.'},{stage:'Advanced',description:'Roots decline and secondary pathogens may develop.'}], lookAlikes: ['Pythium root rot','Underwatering','Nitrogen deficiency'], confirmation: ['Track container weight or substrate water content through dryback.','Inspect roots and drainage.'], immediateActions: ['Pause unnecessary irrigation and restore drainage/oxygenation.'], correctivePlan: ['Adjust shot size, frequency, and media structure to plant demand.'], prevention: ['Use measured dryback rather than a fixed calendar.'], warnings: ['Severe root disease may not recover from irrigation changes alone.'], sources: [], media: [],
  }),
  issue({
    id: 'normal-fade', slug: 'normal-late-flower-fade', name: 'Normal late-flower fade', category: 'Normal development', severity: 'low', reviewStatus: 'provisional', summary: 'Older fan leaves may fade late in reproductive development while flowers and active tissue remain healthy.', affectedParts: ['older fan leaves'], stages: ['late flower'], indicators: ['Older fan leaves fade evenly late in flower','Flowers remain firm and healthy','No spreading lesions, pests, or distorted growth'], exclusions: ['Rapid decline occurs early in flower','Mold, webbing, lesions, or root damage is present','New growth is strongly affected'], progression: [{stage:'Late flower',description:'Older leaves gradually lose color as reproductive development completes.'}], lookAlikes: ['Nitrogen deficiency','Root stress','Systemic disease'], confirmation: ['Confirm stage, progression rate, and health of flowers and roots.'], immediateActions: ['Continue monitoring; do not react to color alone.'], correctivePlan: ['Correct only measured problems.'], prevention: ['Maintain records from healthy plants of the same cultivar.'], warnings: ['Normal senescence does not rule out a simultaneous disease.'], sources: [], media: [],
  }),
]

export const categoryOrder = [
  'Nutrient deficiency','Nutrient toxicity','Insect','Mite','Fungal pathogen','Bacterial pathogen','Root pathogen','Viroid','Virus','Phytoplasma / Spiroplasma','Genetic / developmental','Environmental stress','Water / root-zone','Normal development','Insufficient evidence',
] as const

export const symptomOptions = Array.from(new Set(issues.flatMap((item) => item.indicators))).sort()
