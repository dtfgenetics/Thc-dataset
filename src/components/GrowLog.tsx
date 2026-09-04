import { NotebookPen, Plus, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { makeId } from '../lib/diagnostics'
import type { GrowLogEntry, InvestigationCase } from '../types'

const STORAGE_KEY = 'thc-grow-doc:log:v2'

function loadEntries(): GrowLogEntry[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as GrowLogEntry[] } catch { return [] }
}

interface GrowLogProps {
  investigation: InvestigationCase
}

export function GrowLog({ investigation }: GrowLogProps) {
  const [entries, setEntries] = useState<GrowLogEntry[]>(loadEntries)
  const [formOpen, setFormOpen] = useState(false)
  const [plantName, setPlantName] = useState(investigation.plantName)
  const [note, setNote] = useState('')
  const [outcome, setOutcome] = useState('Monitoring')

  const caseEntries = useMemo(
    () => entries.filter((entry) => entry.investigationId === investigation.id || entry.plantName === investigation.plantName),
    [entries, investigation.id, investigation.plantName],
  )

  const save = () => {
    if (!plantName.trim() || !note.trim()) return
    const nextEntry: GrowLogEntry = {
      id: makeId('log'),
      createdAt: new Date().toISOString(),
      plantName: plantName.trim(),
      note: note.trim(),
      outcome,
      stage: investigation.context.stage || undefined,
      medium: investigation.context.medium || undefined,
      ph: investigation.context.ph || undefined,
      ec: investigation.context.ec || undefined,
      watering: investigation.context.watering || undefined,
      symptoms: investigation.context.symptoms,
      recentChanges: investigation.context.recentChanges || undefined,
      investigationId: investigation.id,
      diagnosisIssueSlug: investigation.diagnosis?.leadingIssueSlug,
      diagnosisConfidence: investigation.diagnosis?.confidence,
    }
    const next = [nextEntry, ...entries]
    setEntries(next)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    setNote('')
    setOutcome('Monitoring')
    setFormOpen(false)
  }

  const remove = (id: string) => {
    const next = entries.filter((entry) => entry.id !== id)
    setEntries(next)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  }

  return (
    <div className="view-container log-view">
      <div className="view-intro">
        <div>
          <span>Investigation history</span>
          <h1>Grow log</h1>
          <p>Follow the active plant over time. New entries capture the current stage, root-zone context, symptoms, and leading differential so later observations can be compared against the same case.</p>
        </div>
        <button className="primary-button compact-button" onClick={() => { setPlantName(investigation.plantName); setFormOpen(true) }}><Plus size={18} /> Add follow-up</button>
      </div>

      <section className="missing-evidence">
        <strong>Active investigation: {investigation.plantName}</strong>
        <p>
          {investigation.diagnosis?.leadingIssueName
            ? `Leading hypothesis: ${investigation.diagnosis.leadingIssueName} (${investigation.diagnosis.confidence ?? 'unrated'} evidence match).`
            : 'No ranked differential has been saved for this investigation yet.'}
        </p>
        <p>
          {[investigation.context.stage, investigation.context.medium, investigation.context.ph && `pH ${investigation.context.ph}`, investigation.context.ec && `EC ${investigation.context.ec}`]
            .filter(Boolean)
            .join(' · ') || 'Add stage and root-zone measurements in Diagnose to establish a stronger baseline.'}
        </p>
      </section>

      {formOpen ? (
        <section className="log-form">
          <h2>New follow-up observation</h2>
          <div>
            <label>Plant or run name<input value={plantName} onChange={(e) => setPlantName(e.target.value)} placeholder="e.g. Blue Mango – plant 3" /></label>
            <label>Outcome
              <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
                <option>Monitoring</option>
                <option>Improving</option>
                <option>Stable</option>
                <option>Worsening</option>
                <option>Resolved</option>
              </select>
            </label>
            <label>Observation<textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Describe new growth, symptom progression, measurements, intervention, and response" /></label>
          </div>
          <div>
            <button className="secondary-button" onClick={() => setFormOpen(false)}>Cancel</button>
            <button className="primary-button" disabled={!plantName.trim() || !note.trim()} onClick={save}>Save follow-up</button>
          </div>
        </section>
      ) : null}

      {caseEntries.length ? (
        <div className="log-list">
          {caseEntries.map((entry) => (
            <article key={entry.id}>
              <div className="log-date"><strong>{new Date(entry.createdAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</strong><span>{new Date(entry.createdAt).getFullYear()}</span></div>
              <div>
                <span>{entry.outcome}</span>
                <h2>{entry.plantName}</h2>
                <p>{entry.note}</p>
                <small>
                  {[entry.stage, entry.medium, entry.ph && `pH ${entry.ph}`, entry.ec && `EC ${entry.ec}`, entry.diagnosisConfidence && `${entry.diagnosisConfidence} differential`]
                    .filter(Boolean)
                    .join(' · ')}
                </small>
                {entry.symptoms?.length ? <small>Symptoms: {entry.symptoms.join(' · ')}</small> : null}
              </div>
              <button onClick={() => remove(entry.id)} aria-label={`Delete log entry for ${entry.plantName}`}><Trash2 /></button>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state"><NotebookPen /><h2>No follow-ups saved for this investigation</h2><p>Save a diagnosis, then record subsequent measurements and plant response here so the case becomes longitudinal evidence rather than a one-time snapshot.</p></div>
      )}
    </div>
  )
}
