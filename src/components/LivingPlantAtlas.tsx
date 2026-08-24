import { useMemo, useState } from 'react'
import { Activity, CheckCircle2, Leaf, Microscope, Network, SearchCheck } from 'lucide-react'

type AtlasSection = {
  id: string
  label: string
  clickLabel: string
  summary: string
  firstAsset: string
  topics: string[]
  metrics: string[]
}

type LeafPage = {
  title: string
  type: 'anatomy' | 'process' | 'diagnostic' | 'environment'
  summary: string
  asset: string
}

const atlasSections: AtlasSection[] = [
  {
    id: 'seed_germination',
    label: 'Seed & Germination',
    clickLabel: 'Seed',
    summary: 'Seed anatomy, viability, germination conditions, radicle emergence, cotyledons, seedling transition, storage, and early failure points.',
    firstAsset: 'Annotated seed anatomy plate',
    topics: ['Seed anatomy', 'Seed viability', 'Imbibition', 'Radicle emergence', 'Cotyledons', 'Seed storage'],
    metrics: ['temperature', 'moisture', 'oxygen access', 'time since sowing'],
  },
  {
    id: 'root_system',
    label: 'Root System',
    clickLabel: 'Roots',
    summary: 'Root structure, root hairs, rhizosphere, oxygen availability, water uptake, nutrient uptake, dryback, media interaction, and root disorders.',
    firstAsset: 'Root-zone cutaway diagram',
    topics: ['Primary root', 'Lateral roots', 'Root hairs', 'Rhizosphere', 'Root oxygen', 'Water uptake', 'Nutrient uptake', 'Dryback'],
    metrics: ['substrate moisture', 'pH', 'EC', 'water temperature'],
  },
  {
    id: 'stem_vascular',
    label: 'Stem & Vascular System',
    clickLabel: 'Stem',
    summary: 'Stem structure, support, xylem, phloem, transport, internodal spacing, stem elongation, damage response, and training response.',
    firstAsset: 'Stem cross-section infographic',
    topics: ['Xylem', 'Phloem', 'Stem elongation', 'Internodal spacing', 'Transport', 'Training response'],
    metrics: ['growth rate', 'internode length', 'light intensity', 'air movement'],
  },
  {
    id: 'nodes_branching',
    label: 'Nodes & Branching',
    clickLabel: 'Nodes',
    summary: 'Nodes, internodes, axillary buds, branch formation, apical dominance, pruning, topping, FIM, LST, mainlining, and SCROG.',
    firstAsset: 'Node anatomy diagram',
    topics: ['Node anatomy', 'Internodes', 'Axillary buds', 'Apical dominance', 'Topping', 'LST', 'SCROG'],
    metrics: ['node count', 'internode length', 'canopy height', 'training date'],
  },
  {
    id: 'leaves',
    label: 'Leaves',
    clickLabel: 'Leaves',
    summary: 'Leaf anatomy, photosynthesis, stomata, transpiration, chlorosis, necrosis, leaf curl, nutrient clues, pest damage, and environmental stress.',
    firstAsset: 'Healthy fan leaf reference plate',
    topics: ['Leaf anatomy', 'Photosynthesis', 'Stomata', 'Transpiration', 'Chlorosis', 'Necrosis', 'Leaf curl', 'Pest damage'],
    metrics: ['PPFD', 'DLI', 'VPD', 'temperature', 'RH', 'pH', 'EC'],
  },
  {
    id: 'flowers',
    label: 'Flowers',
    clickLabel: 'Flowers',
    summary: 'Flower initiation, pistils/stigmas, bracts, bud development, resin, pollination, maturation, harvest timing, and mold risk.',
    firstAsset: 'Flower anatomy plate',
    topics: ['Flower initiation', 'Bracts', 'Pistils', 'Stigmas', 'Bud development', 'Pollination', 'Mold risk'],
    metrics: ['photoperiod', 'DLI', 'RH', 'VPD', 'flowering week'],
  },
  {
    id: 'trichomes_resin',
    label: 'Trichomes & Resin',
    clickLabel: 'Trichomes',
    summary: 'Trichome types, resin glands, glandular structures, maturity cues, microscope inspection, and harvest interpretation.',
    firstAsset: 'Trichome maturity chart',
    topics: ['Capitate-stalked trichomes', 'Capitate-sessile trichomes', 'Bulbous trichomes', 'Resin glands', 'Microscope inspection'],
    metrics: ['magnification', 'flowering week', 'environmental conditions'],
  },
  {
    id: 'sex_pollen_seed',
    label: 'Sex, Pollen & Seeds',
    clickLabel: 'Sex / Seed',
    summary: 'Female flowers, male flowers, hermaphroditism, pollen sacs, pollination, fertilization, seed formation, seed maturity, and breeding basics.',
    firstAsset: 'Male vs female flower comparison',
    topics: ['Female flowers', 'Male flowers', 'Hermaphroditism', 'Pollen sacs', 'Pollination', 'Seed formation'],
    metrics: ['days since pollination', 'flowering stage', 'humidity', 'storage conditions'],
  },
  {
    id: 'environment_overlay',
    label: 'Environment Overlay',
    clickLabel: 'Environment',
    summary: 'Whole-plant overlay for light, temperature, humidity, VPD, airflow, water, nutrients, pH, EC, CO2, and their interactions.',
    firstAsset: 'Environmental interaction map',
    topics: ['Light', 'Temperature', 'Humidity', 'VPD', 'Airflow', 'CO2', 'Water', 'Nutrients', 'pH', 'EC'],
    metrics: ['PPFD', 'DLI', 'temperature', 'RH', 'VPD', 'CO2', 'pH', 'EC'],
  },
  {
    id: 'diagnostic_overlay',
    label: 'Diagnostic Overlay',
    clickLabel: 'Diagnostics',
    summary: 'Symptom-location system for yellowing, browning, spots, curling, wilting, burnt tips, stunting, pest signs, mold signs, and root-zone clues.',
    firstAsset: 'Symptom location map',
    topics: ['Yellowing', 'Browning', 'Spots', 'Curling', 'Wilting', 'Burnt tips', 'Pest signs', 'Root symptoms'],
    metrics: ['pH', 'EC', 'VPD', 'temperature', 'RH', 'substrate moisture', 'light intensity'],
  },
]

const leafPages: LeafPage[] = [
  { title: 'Leaf Anatomy', type: 'anatomy', summary: 'Healthy cannabis leaf structure becomes the baseline for interpreting plant stress.', asset: 'Healthy Fan Leaf Reference Card' },
  { title: 'Photosynthesis', type: 'process', summary: 'How leaves use light, carbon dioxide, and water to produce sugars that support growth.', asset: 'Photosynthesis Flow Card' },
  { title: 'Stomata', type: 'anatomy', summary: 'Microscopic pores that connect CO2 entry, water vapor loss, VPD, and transpiration.', asset: 'Stomata and VPD Card' },
  { title: 'Transpiration', type: 'process', summary: 'Water movement from roots through xylem and out of leaves as vapor.', asset: 'Transpiration Flow Card' },
  { title: 'Chlorosis', type: 'diagnostic', summary: 'Yellowing patterns that narrow possibilities but do not prove a single cause.', asset: 'Chlorosis Pattern Checklist' },
  { title: 'Necrosis', type: 'diagnostic', summary: 'Dead plant tissue shown as burnt tips, brown margins, spots, blotches, or lesions.', asset: 'Necrosis Evaluation Card' },
  { title: 'Leaf Curl', type: 'diagnostic', summary: 'Posture changes such as tacoing, clawing, drooping, twisting, and cupping.', asset: 'Leaf Curl Pattern Guide' },
  { title: 'Nutrient Symptoms on Leaves', type: 'diagnostic', summary: 'Visual nutrient clues interpreted with pH, EC, feed history, root health, and environment.', asset: 'Nutrient Symptom Triage Card' },
  { title: 'Pest Damage on Leaves', type: 'diagnostic', summary: 'Stippling, webbing, trails, eggs, frass, silvering, chewing, and distorted growth.', asset: 'Leaf Pest Inspection Card' },
  { title: 'Environmental Stress on Leaves', type: 'environment', summary: 'Leaf posture, color, texture, growth rate, and damage location caused by environment.', asset: 'Environmental Leaf Stress Checklist' },
]

const hotspotClass: Record<string, string> = {
  seed_germination: 'seed',
  root_system: 'roots',
  stem_vascular: 'stem-target',
  nodes_branching: 'nodes',
  leaves: 'leaves',
  flowers: 'flowers',
  trichomes_resin: 'trichomes',
  sex_pollen_seed: 'sex',
  environment_overlay: 'environment',
  diagnostic_overlay: 'diagnostics',
}

export function LivingPlantAtlas() {
  const [activeId, setActiveId] = useState('leaves')
  const activeSection = useMemo(() => atlasSections.find((section) => section.id === activeId) ?? atlasSections[4], [activeId])

  return (
    <div className="atlas-page">
      <section className="atlas-hero-panel">
        <div>
          <p className="section-kicker">THC Living Plant Atlas</p>
          <h1>The plant becomes the interface.</h1>
          <p>
            Click a plant structure or overlay to connect anatomy, physiology, diagnostics, measurements, image references, and field cards.
          </p>
        </div>
        <div className="atlas-rule-card">
          <SearchCheck size={28} />
          <strong>Observation first. Diagnosis second.</strong>
          <span>A symptom is evidence, not proof. Confirm with environment, root-zone data, plant stage, pest inspection, and recent changes.</span>
        </div>
      </section>

      <section className="atlas-layout">
        <div className="atlas-plant-stage" aria-label="Clickable Living Plant Atlas prototype">
          <div className="atlas-sun" />
          <div className="atlas-flower" />
          <div className="atlas-leaf atlas-leaf-a" />
          <div className="atlas-leaf atlas-leaf-b" />
          <div className="atlas-leaf atlas-leaf-c" />
          <div className="atlas-leaf atlas-leaf-d" />
          <div className="atlas-node atlas-node-a" />
          <div className="atlas-node atlas-node-b" />
          <div className="atlas-node atlas-node-c" />
          <div className="atlas-stem" />
          <div className="atlas-soil" />
          <div className="atlas-root"><span /><i /></div>
          {atlasSections.map((section) => (
            <button
              key={section.id}
              className={`atlas-hotspot ${hotspotClass[section.id]} ${activeId === section.id ? 'active' : ''}`}
              onClick={() => setActiveId(section.id)}
              type="button"
            >
              {section.clickLabel}
            </button>
          ))}
        </div>

        <article className="atlas-info-card">
          <p className="section-kicker">Atlas Section</p>
          <h2>{activeSection.label}</h2>
          <p>{activeSection.summary}</p>
          <div className="atlas-callout"><strong>First asset:</strong> {activeSection.firstAsset}</div>
          <h3>Core topics</h3>
          <div className="pill-grid">{activeSection.topics.map((topic) => <span key={topic}>{topic}</span>)}</div>
          <h3>Related measurements</h3>
          <div className="pill-grid muted">{activeSection.metrics.map((metric) => <span key={metric}>{metric}</span>)}</div>
        </article>
      </section>

      <section className="atlas-system-grid">
        <article><Leaf size={30} /><h3>Leaf Module v1</h3><p>First production module because leaves show the most visible early symptoms.</p></article>
        <article><Microscope size={30} /><h3>Reference Images</h3><p>Built to support future image/video analysis with structured visual evidence.</p></article>
        <article><Network size={30} /><h3>Knowledge Graph Ready</h3><p>Every section can connect to symptoms, measurements, glossary terms, and datasets.</p></article>
        <article><Activity size={30} /><h3>Diagnostics Overlay</h3><p>Symptom-location mapping keeps diagnosis contextual instead of guessing from one photo.</p></article>
      </section>

      <section className="leaf-module-panel">
        <div className="leaf-module-header">
          <p className="section-kicker">First Build Module</p>
          <h2>Leaf Module v1</h2>
          <p>These pages should be expanded into full lessons, illustrated field cards, and diagnostic image references.</p>
        </div>
        <div className="leaf-page-grid">
          {leafPages.map((page) => (
            <article className="leaf-page-card" key={page.title}>
              <span>{page.type}</span>
              <h3>{page.title}</h3>
              <p>{page.summary}</p>
              <strong><CheckCircle2 size={16} /> {page.asset}</strong>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
