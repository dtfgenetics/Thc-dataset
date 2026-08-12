import { NotebookPen, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { makeId } from '../lib/diagnostics'
import type { GrowLogEntry } from '../types'

const STORAGE_KEY = 'thc-grow-doc:log:v1'

function loadEntries(): GrowLogEntry[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as GrowLogEntry[] } catch { return [] }
}

export function GrowLog() {
  const [entries, setEntries] = useState<GrowLogEntry[]>(loadEntries)
  const [formOpen, setFormOpen] = useState(false)
  const [plantName, setPlantName] = useState('')
  const [note, setNote] = useState('')

  const save = () => {
    if (!plantName.trim() || !note.trim()) return
    const next = [{ id: makeId('log'), createdAt: new Date().toISOString(), plantName: plantName.trim(), note: note.trim(), outcome: 'Monitoring' }, ...entries]
    setEntries(next); localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); setPlantName(''); setNote(''); setFormOpen(false)
  }
  const remove = (id: string) => { const next = entries.filter((entry) => entry.id !== id); setEntries(next); localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) }

  return (
    <div className="view-container log-view">
      <div className="view-intro"><div><span>Follow-up history</span><h1>Grow log</h1><p>Record what changed and whether the plant improved. This build stores entries in this browser only.</p></div><button className="primary-button compact-button" onClick={() => setFormOpen(true)}><Plus size={18} /> Add entry</button></div>
      {formOpen ? <section className="log-form"><h2>New observation</h2><div><label>Plant or run name<input value={plantName} onChange={(e) => setPlantName(e.target.value)} placeholder="e.g. Blue Mango – plant 3" /></label><label>Observation<textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Symptoms, environment, action taken, and response" /></label></div><div><button className="secondary-button" onClick={() => setFormOpen(false)}>Cancel</button><button className="primary-button" disabled={!plantName.trim() || !note.trim()} onClick={save}>Save entry</button></div></section> : null}
      {entries.length ? <div className="log-list">{entries.map((entry) => <article key={entry.id}><div className="log-date"><strong>{new Date(entry.createdAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</strong><span>{new Date(entry.createdAt).getFullYear()}</span></div><div><span>{entry.outcome}</span><h2>{entry.plantName}</h2><p>{entry.note}</p></div><button onClick={() => remove(entry.id)} aria-label={`Delete log entry for ${entry.plantName}`}><Trash2 /></button></article>)}</div> : <div className="empty-state"><NotebookPen /><h2>No observations saved yet</h2><p>Use the log after a diagnosis to compare new growth and document whether the corrective action worked.</p></div>}
    </div>
  )
}
