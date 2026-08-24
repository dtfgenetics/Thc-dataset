import { useMemo, useState } from 'react'
import { AppShell } from './components/AppShell'
import { About } from './components/About'
import { CoverageDashboard } from './components/CoverageDashboard'
import { DiagnosticResult } from './components/DiagnosticResult'
import { EvidenceUploader } from './components/EvidenceUploader'
import { GrowContextForm } from './components/GrowContextForm'
import { GrowLog } from './components/GrowLog'
import { IssueLibrary } from './components/IssueLibrary'
import { LivingPlantAtlas } from './components/LivingPlantAtlas'
import './components/LivingPlantAtlas.css'
import { ReferenceLibrary } from './components/ReferenceLibrary'
import { VisualObservationReview } from './components/VisualObservationReview'
import { issues } from './data/catalog'
import { inspectEvidenceFile, makeId, rankDifferentials } from './lib/diagnostics'
import type { EvidenceFile, EvidenceSlot, GrowContext, View } from './types'

const emptyContext: GrowContext = { stage: '', medium: '', ph: '', ec: '', watering: '', recentChanges: '', symptoms: [] }

export default function App() {
  const [view, setView] = useState<View>('atlas')
  const [evidence, setEvidence] = useState<EvidenceFile[]>([])
  const [context, setContext] = useState<GrowContext>(emptyContext)
  const [reviewed, setReviewed] = useState(false)
  const [issueSlug, setIssueSlug] = useState<string>()
  const results = useMemo(() => reviewed ? rankDifferentials(issues, context, evidence) : [], [context, evidence, reviewed])

  const handleFiles = async (slot: EvidenceSlot, fileList: FileList) => {
    const files = [...fileList].slice(0, slot === 'close-up' ? 4 : 1)
    const additions = files.map((file) => ({ id: makeId('evidence'), file, previewUrl: URL.createObjectURL(file), slot, quality: 'checking' as const, notes: [] }))
    setReviewed(false)
    setEvidence((current) => {
      current.filter((item) => item.slot === slot).forEach((item) => URL.revokeObjectURL(item.previewUrl))
      return slot === 'close-up' ? [...current.filter((item) => item.slot !== slot), ...additions] : [...current.filter((item) => item.slot !== slot), additions[0]]
    })
    await Promise.all(additions.map(async (addition) => { const inspection = await inspectEvidenceFile(addition.file); setEvidence((current) => current.map((item) => item.id === addition.id ? { ...item, ...inspection } : item)) }))
  }

  const removeFile = (id: string) => { setEvidence((current) => { const target = current.find((item) => item.id === id); if (target) URL.revokeObjectURL(target.previewUrl); return current.filter((item) => item.id !== id) }); setReviewed(false) }
  const openIssue = (slug: string) => { setIssueSlug(slug); setView('issues') }
  const applyVisualObservations = (indicators: string[]) => {
    setContext((current) => ({ ...current, symptoms: [...new Set([...current.symptoms, ...indicators])] }))
    setReviewed(false)
  }

  return (
    <AppShell activeView={view} onViewChange={setView}>
      {view === 'atlas' ? <LivingPlantAtlas /> : null}
      {view === 'diagnose' ? (
        <div className="diagnostic-page">
          <div className="diagnostic-layout"><div className="workflow-column"><EvidenceUploader evidence={evidence} onFiles={handleFiles} onRemove={removeFile} /><VisualObservationReview evidence={evidence} selectedSymptoms={context.symptoms} onApply={applyVisualObservations} /><GrowContextForm context={context} onChange={(next) => { setContext(next); setReviewed(false) }} /></div><DiagnosticResult evidence={evidence} context={context} results={results} reviewed={reviewed} onReview={() => setReviewed(true)} onOpenIssue={openIssue} /></div>
        </div>
      ) : null}
      {view === 'issues' ? <IssueLibrary initialSlug={issueSlug} onClearInitialSlug={() => setIssueSlug(undefined)} /> : null}
      {view === 'references' ? <ReferenceLibrary onOpenIssue={openIssue} /> : null}
      {view === 'coverage' ? <CoverageDashboard /> : null}
      {view === 'log' ? <GrowLog /> : null}
      {view === 'about' ? <About /> : null}
    </AppShell>
  )
}
