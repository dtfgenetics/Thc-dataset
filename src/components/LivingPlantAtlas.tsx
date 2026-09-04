import { useEffect, useMemo, useState } from 'react'
import { Activity, CheckCircle2, Leaf, Microscope, Network, SearchCheck } from 'lucide-react'
import type { InvestigationCase, IssueRecord } from '../types'

type AtlasSection = {
  id: string
  label: string
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
  { id: 'seed_germination', label: 'Seed & Germination', summary: 'Seed anatomy, viability, germination conditions, radicle emergence, cotyledons, seedling transition, storage, and early failure points.', firstAsset: 'Annotated seed anatomy plate', topics: ['Seed anatomy', 'Seed viability', 'Imbibition', 'Radicle emergence', 'Cotyledons', 'Seed storage'], metrics: ['temperature', 'moisture', 'oxygen access', 'time since sowing'] },
  { id: 'root_system', label: 'Root System', summary: 'Root structure, root hairs, rhizosphere, oxygen availability, water uptake, nutrient uptake, dryback, media interaction, and root disorders.', firstAsset: 'Root-zone cutaway diagram', topics: ['Primary root', 'Lateral roots', 'Root hairs', 'Rhizosphere', 'Root oxygen', 'Water uptake', 'Nutrient uptake', 'Dryback'], metrics: ['substrate moisture', 'pH', 'EC', 'water temperature'] },
  { id: 'stem_vascular', label: 'Stem & Vascular System', summary: 'Stem structure, support, xylem, phloem, transport, internodal spacing, stem elongation, damage response, and training response.', firstAsset: 'Stem cross-section infographic', topics: ['Xylem', 'Phloem', 'Stem elongation', 'Internodal spacing', 'Transport', 'Training response'], metrics: ['growth rate', 'internode length', 'light intensity', 'air movement'] },
  { id: 'nodes_branching', label: 'Nodes & Branching', summary: 'Nodes, internodes, axillary buds, branch formation, apical dominance, pruning, topping, FIM, LST, mainlining, and SCROG.', firstAsset: 'Node anatomy diagram', topics: ['Node anatomy', 'Internodes', 'Axillary buds', 'Apical dominance', 'Topping', 'LST', 'SCROG'], metrics: ['node count', 'internode length', 'canopy height', 'training date'] },
  { id: 'leaves', label: 'Leaves', summary: 'Leaf anatomy, photosynthesis, stomata, transpiration, chlorosis, necrosis, leaf curl, nutrient clues, pest damage, and environmental stress.', firstAsset: 'Healthy fan leaf reference plate', topics: ['Leaf anatomy', 'Photosynthesis', 'Stomata', 'Transpiration', 'Chlorosis', 'Necrosis', 'Leaf curl', 'Pest damage'], metrics: ['PPFD', 'DLI', 'VPD', 'temperature', 'RH', 'pH', 'EC'] },
  { id: 'flowers', label: 'Flowers', summary: 'Flower initiation, pistils/stigmas, bracts, bud development, resin, pollination, maturation, harvest timing, and mold risk.', firstAsset: 'Flower anatomy plate', topics: ['Flower initiation', 'Bracts', 'Pistils', 'Stigmas', 'Bud development', 'Pollination', 'Mold risk'], metrics: ['photoperiod', 'DLI', 'RH', 'VPD', 'flowering week'] },
  { id: 'trichomes_resin', label: 'Trichomes & Resin', summary: 'Trichome types, resin glands, glandular structures, maturity cues, microscope inspection, and harvest interpretation.', firstAsset: 'Trichome maturity chart', topics: ['Capitate-stalked trichomes', 'Capitate-sessile trichomes', 'Bulbous trichomes', 'Resin glands', 'Microscope inspection'], metrics: ['magnification', 'flowering week', 'environmental conditions'] },
  { id: 'sex_pollen_seed', label: 'Sex, Pollen & Seeds', summary: 'Female flowers, male flowers, hermaphroditism, pollen sacs, pollination, fertilization, seed formation, seed maturity, and breeding basics.', firstAsset: 'Male vs female flower comparison', topics: ['Female flowers', 'Male flowers', 'Hermaphroditism', 'Pollen sacs', 'Pollination', 'Seed formation'], metrics: ['days since pollination', 'flowering stage', 'humidity', 'storage conditions'] },
  { id: 'environment_overlay', label: 'Environment Overlay', summary: 'Whole-plant context for light, temperature, humidity, VPD, airflow, water, nutrients, pH, EC, CO2, and their interactions.', firstAsset: 'Environmental interaction map', topics: ['Light', 'Temperature', 'Humidity', 'VPD', 'Airflow', 'CO2', 'Water', 'Nutrients', 'pH', 'EC'], metrics: ['PPFD', 'DLI', 'temperature', 'RH', 'VPD', 'CO2', 'pH', 'EC'] },
  { id: 'diagnostic_overlay', label: 'Diagnostic Overlay', summary: 'Symptom-location system for yellowing, browning, spots, curling, wilting, burnt tips, stunting, pest signs, mold signs, and root-zone clues.', firstAsset: 'Symptom location map', topics: ['Yellowing', 'Browning', 'Spots', 'Curling', 'Wilting', 'Burnt tips', 'Pest signs', 'Root symptoms'], metrics: ['pH', 'EC', 'VPD', 'temperature', 'RH', 'substrate moisture', 'light intensity'] },
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

function sectionForIssue(issue?: IssueRecord) {
  const parts = (issue?.affectedParts ?? []).join(' ').toLowerCase()
  if (/root|crown|rhiz|substrate/.test(parts)) return 'root_system'
  if (/flower|bud|bract|pistil|inflorescence/.test(parts)) return 'flowers'
  if (/stem|vascular|xylem|phloem/.test(parts)) return 'stem_vascular'
  if (/node|internode|branch|meristem|shoot/.test(parts)) return 'nodes_branching'
  if (/seed|cotyledon|radicle|seedling/.test(parts)) return 'seed_germination'
  if (/trichome|resin|gland/.test(parts)) return 'trichomes_resin'
  if (/leaf|leaves|foliar/.test(parts)) return 'leaves'
  if (issue?.category === 'Environmental stress' || issue?.category === 'Water / root-zone') return 'environment_overlay'
  return 'diagnostic_overlay'
}

export function LivingPlantAtlas({ investigation, issue }: { investigation?: InvestigationCase; issue?: IssueRecord }) {
  const suggestedSection = useMemo(() => sectionForIssue(issue), [issue])
  const [activeId, setActiveId] = useState(suggestedSection)
  useEffect(() => setActiveId(suggestedSection), [suggestedSection])
  const activeSection = useMemo(() => atlasSections.find((section) => section.id === activeId) ?? atlasSections[4], [activeId])

  return (
    <div className="atlas-page atlas-page-v2">
      <section className="atlas-hero-v2">
        <div>
          <span>Living Plant Atlas</span>
          <h1>Navigate the plant by evidence, not decoration.</h1>
          <p>Move between plant structures, physiological processes, measurements, diagnostic patterns, and reviewed reference material. Each section is designed to connect what you see with what you should measure next.</p>
        </div>
        <aside className="atlas-principle">
          <SearchCheck size={30} />
          <strong>{issue ? `Investigation focus: ${issue.name}` : 'Observation is the starting point.'}</strong>
          <p>{issue ? `Grow Doc routed this case here from affected structures: ${issue.affectedParts.join(', ') || 'not yet localized'}. Use the measurements below to test the hypothesis.` : 'Visual symptoms can narrow possibilities. They do not replace root-zone data, environment, plant stage, pest inspection, or recent history.'}</p>
          {investigation?.diagnosis?.confidence ? <small>{investigation.diagnosis.confidence} evidence match · case {investigation.id.slice(-6)}</small> : null}
        </aside>
      </section>

      <section className="atlas-workspace-v2">
        <nav className="atlas-section-rail" aria-label="Plant atlas sections">
          <div className="atlas-rail-heading"><span>10 systems</span><strong>Choose a plant system</strong></div>
          {atlasSections.map((section, index) => <button key={section.id} className={activeId === section.id ? 'active' : ''} onClick={() => setActiveId(section.id)} type="button"><span>{String(index + 1).padStart(2, '0')}</span><strong>{section.label}</strong></button>)}
        </nav>

        <article className="atlas-evidence-board">
          <header><span>{activeId === suggestedSection && issue ? 'Suggested from active investigation' : 'Selected system'}</span><h2>{activeSection.label}</h2><p>{activeSection.summary}</p></header>
          <div className="atlas-evidence-callout"><Microscope size={22} /><div><span>Reference target</span><strong>{activeSection.firstAsset}</strong></div></div>
          <div className="atlas-detail-grid">
            <section><span>What to inspect</span><div className="atlas-topic-list">{activeSection.topics.map((topic) => <div key={topic}><CheckCircle2 size={16} /><strong>{topic}</strong></div>)}</div></section>
            <section><span>Measurements that add context</span><div className="atlas-metric-list">{activeSection.metrics.map((metric) => <div key={metric}><Activity size={16} /><strong>{metric}</strong></div>)}</div></section>
          </div>
          {issue ? <div className="atlas-evidence-callout"><Network size={22} /><div><span>Diagnostic question</span><strong>{issue.confirmation[0] ?? 'Gather a discriminating observation before changing the treatment plan.'}</strong></div></div> : null}
        </article>
      </section>

      <section className="atlas-system-strip">
        <article><Leaf size={28} /><div><h3>Anatomy</h3><p>Start with the organ and tissue that changed.</p></div></article>
        <article><Microscope size={28} /><div><h3>Reference evidence</h3><p>Compare against reviewed images with known limitations.</p></div></article>
        <article><Network size={28} /><div><h3>Connected context</h3><p>Link symptoms to measurements, stage, history, and environment.</p></div></article>
        <article><Activity size={28} /><div><h3>Diagnostic follow-up</h3><p>Use the next measurement to separate competing explanations.</p></div></article>
      </section>

      <section className="leaf-module-panel leaf-module-panel-v2">
        <div className="leaf-module-header"><span>Leaf module</span><h2>Start with the most visible diagnostic organ.</h2><p>Leaf observations become useful when structure, process, symptom pattern, and environmental context are kept together.</p></div>
        <div className="leaf-page-grid leaf-page-grid-v2">{leafPages.map((page) => <article className="leaf-page-card" key={page.title}><span>{page.type}</span><h3>{page.title}</h3><p>{page.summary}</p><strong><CheckCircle2 size={16} /> {page.asset}</strong></article>)}</div>
      </section>
    </div>
  )
}
