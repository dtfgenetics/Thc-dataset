import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { symptomOptions } from '../data/catalog'
import type { GrowContext } from '../types'

interface GrowContextFormProps {
  context: GrowContext
  onChange: (context: GrowContext) => void
}

export function GrowContextForm({ context, onChange }: GrowContextFormProps) {
  const [symptomsOpen, setSymptomsOpen] = useState(false)
  const update = <K extends keyof GrowContext>(key: K, value: GrowContext[K]) => onChange({ ...context, [key]: value })
  const toggleSymptom = (symptom: string) => update('symptoms', context.symptoms.includes(symptom) ? context.symptoms.filter((item) => item !== symptom) : [...context.symptoms, symptom])

  return (
    <section className="context-section" aria-labelledby="context-title">
      <div className="section-heading compact">
        <div><span>Step 2</span><h2 id="context-title">Add grow context</h2></div>
        <p>Optional, but measured details help separate look-alikes.</p>
      </div>
      <div className="context-grid">
        <label>Growth stage<select value={context.stage} onChange={(e) => update('stage', e.target.value)}><option value="">Select stage</option><option value="vegetative">Vegetative</option><option value="flower">Flower</option><option value="late flower">Late flower</option><option value="all">Unknown / mixed</option></select></label>
        <label>Growing medium<select value={context.medium} onChange={(e) => update('medium', e.target.value)}><option value="">Select medium</option><option>Coco</option><option>Living soil</option><option>Potting mix</option><option>Rockwool</option><option>Deep-water culture</option><option>Other hydroponic</option><option>Outdoor soil</option></select></label>
        <label>Measured pH<input inputMode="decimal" placeholder="e.g. 6.2" value={context.ph} onChange={(e) => update('ph', e.target.value)} /></label>
        <label>Measured EC / PPM<input placeholder="e.g. 1.4 mS/cm or 700 ppm" value={context.ec} onChange={(e) => update('ec', e.target.value)} /></label>
        <label>Watering routine<select value={context.watering} onChange={(e) => update('watering', e.target.value)}><option value="">Select routine</option><option>Hand-water by dryback</option><option>Fixed schedule</option><option>Automated irrigation</option><option>Recirculating system</option><option>Unknown</option></select></label>
        <label className="full-field">Recent changes<textarea placeholder="Feeding, transplanting, pruning, sprays, equipment failure, weather, or other changes in the last two weeks" value={context.recentChanges} onChange={(e) => update('recentChanges', e.target.value)} /></label>
      </div>

      <div className="symptom-picker">
        <button type="button" onClick={() => setSymptomsOpen((current) => !current)} aria-expanded={symptomsOpen}>
          <span><strong>Visible symptoms</strong><small>{context.symptoms.length ? `${context.symptoms.length} selected` : 'Select only what you can clearly confirm'}</small></span><ChevronDown className={symptomsOpen ? 'rotate' : ''} />
        </button>
        {symptomsOpen ? (
          <div className="symptom-options">
            {symptomOptions.map((symptom) => <button type="button" key={symptom} className={context.symptoms.includes(symptom) ? 'selected' : ''} onClick={() => toggleSymptom(symptom)}>{context.symptoms.includes(symptom) ? <CheckMini /> : null}{symptom}</button>)}
          </div>
        ) : null}
      </div>
    </section>
  )
}

function CheckMini() {
  return <span aria-hidden="true">✓</span>
}
