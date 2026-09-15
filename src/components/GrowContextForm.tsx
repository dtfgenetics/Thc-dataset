import { ChevronDown, Gauge, ListChecks } from 'lucide-react'
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
  const contextCount = [context.stage, context.medium, context.ph, context.ec, context.watering, context.recentChanges].filter(Boolean).length

  return (
    <section className="context-section" aria-labelledby="context-title">
      <div className="section-heading compact">
        <div><span>Optional</span><h2 id="context-title">Add details only if you know them</h2></div>
        <p>Measurements can improve a close call, but they should not stand between you and the first review.</p>
      </div>

      <details className="context-disclosure">
        <summary>
          <Gauge size={20} />
          <span><strong>Grow measurements & recent changes</strong><small>{contextCount ? `${contextCount} field${contextCount === 1 ? '' : 's'} added` : 'Stage, medium, pH, EC, watering, recent changes'}</small></span>
          <ChevronDown />
        </summary>
        <div className="context-grid">
          <label>Growth stage<select value={context.stage} onChange={(e) => update('stage', e.target.value)}><option value="">Select stage</option><option value="vegetative">Vegetative</option><option value="flower">Flower</option><option value="late flower">Late flower</option><option value="all">Unknown / mixed</option></select></label>
          <label>Growing medium<select value={context.medium} onChange={(e) => update('medium', e.target.value)}><option value="">Select medium</option><option>Coco</option><option>Living soil</option><option>Potting mix</option><option>Rockwool</option><option>Deep-water culture</option><option>Other hydroponic</option><option>Outdoor soil</option></select></label>
          <label>Measured pH<input inputMode="decimal" placeholder="e.g. 6.2" value={context.ph} onChange={(e) => update('ph', e.target.value)} /></label>
          <label>Measured EC / PPM<input placeholder="e.g. 1.4 mS/cm or 700 ppm" value={context.ec} onChange={(e) => update('ec', e.target.value)} /></label>
          <label>Watering routine<select value={context.watering} onChange={(e) => update('watering', e.target.value)}><option value="">Select routine</option><option>Hand-water by dryback</option><option>Fixed schedule</option><option>Automated irrigation</option><option>Recirculating system</option><option>Unknown</option></select></label>
          <label className="full-field">Recent changes<textarea placeholder="Feed changes, transplanting, pruning, sprays, equipment failure, weather, or other changes" value={context.recentChanges} onChange={(e) => update('recentChanges', e.target.value)} /></label>
        </div>
      </details>

      <div className="symptom-picker">
        <button type="button" onClick={() => setSymptomsOpen((current) => !current)} aria-expanded={symptomsOpen}>
          <ListChecks size={20} />
          <span><strong>Manually confirm visible signs</strong><small>{context.symptoms.length ? `${context.symptoms.length} selected` : 'Use this only for signs you can clearly see'}</small></span><ChevronDown className={symptomsOpen ? 'rotate' : ''} />
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
