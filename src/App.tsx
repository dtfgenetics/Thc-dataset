import { useMemo, useState } from 'react'
import { AppShell } from './components/AppShell'
import { About } from './components/About'
import { CoverageDashboard } from './components/CoverageDashboard'
import { DiagnosticResult } from './components/DiagnosticResult'
import { EvidenceUploader } from './components/EvidenceUploader'
import { GrowContextForm } from './components/GrowContextForm'
import { GrowLog } from './components/GrowLog'
import { InvestigationManager } from './components/InvestigationManager'
import { IssueLibrary } from './components/IssueLibrary'
import { LivingPlantAtlas } from './components/LivingPlantAtlas'
import './components/LivingPlantAtlas.css'
import { ReferenceLibrary } from './components/ReferenceLibrary'
import { VisualObservationReview } from './components/VisualObservationReview'
import { issues } from './data/catalog'
import { summarizeCaseTrend } from './lib/case-trends'
import { inspectEvidenceFile, makeId, rankDifferentials } from './lib/diagnostics'
import { activateInvestigation, createInvestigation, loadActiveInvestigation, loadInvestigations, upsertInvestigation } from './lib/investigations'
import type { DiagnosticSnapshot, EvidenceFile, EvidenceSlot, GrowContext, GrowLogEntry, InvestigationCase, View } from './types'

const emptyContext: GrowContext = { stage: '', medium: '', ph: '', ec: '', watering: '', recentChanges: '', symptoms: [] }
const LOG_KEY = 'thc-grow-doc:log:v2'

function loadLogEntries(): GrowLogEntry[] {
  try { return JSON.parse(localStorage.getItem(LOG_KEY) ?? '[]') as GrowLogEntry[] } catch { return [] }
}

export default function App() {
  const restored = useMemo(loadActiveInvestigation, [])
  const [view, setView] = useState<View>('diagnose')
  const [evidence, setEvidence] = useState<EvidenceFile[]>([])
  const [context, setContext] = useState<GrowContext>(restored.context ?? emptyContext)
  const [reviewed, setReviewed] = useState(false)
  const [issueSlug, setIssueSlug] = useState<string>()
  const [historyRevision, setHistoryRevision] = useState(0)
  const [investigation, setInvestigation] = useState<InvestigationCase>(restored)
  const [investigations, setInvestigations] = useState<InvestigationCase[]>(() => loadInvestigations())

  const caseHistory = useMemo(() => loadLogEntries().filter((entry) => entry.investigationId === investigation.id), [investigation.id, historyRevision])
  const results = useMemo(() => reviewed ? rankDifferentials(issues, context, evidence, caseHistory) : [], [context, evidence, reviewed, caseHistory])
  const caseTrend = useMemo(() => summarizeCaseTrend(context, caseHistory, results), [context, caseHistory, results])
  const leadingIssue = useMemo(() => issues.find((issue) => issue.slug === investigation.diagnosis?.leadingIssueSlug), [investigation.diagnosis?.leadingIssueSlug])
  const referenceFocusSlugs = useMemo(() => [investigation.diagnosis?.leadingIssueSlug, ...(investigation.diagnosis?.alternativeIssueSlugs ?? [])].filter((slug): slug is string => Boolean(slug)), [investigation.diagnosis])

  const replaceInvestigation = (next: InvestigationCase) => {
    setInvestigation(next)
    setInvestigations(upsertInvestigation(next))
  }

  const syncInvestigation = (nextContext: GrowContext, diagnosis?: DiagnosticSnapshot) => {
    setInvestigation((current) => {
      const diagnosisHistory = diagnosis
        ? [...(current.diagnosisHistory ?? []), diagnosis].slice(-30)
        : current.diagnosisHistory
      const next: InvestigationCase = {
        ...current,
        updatedAt: new Date().toISOString(),
        context: nextContext,
        evidenceSummary: evidence.map((item) => ({ slot: item.slot, quality: item.quality, notes: item.notes })),
        diagnosis: diagnosis ?? current.diagnosis,
        diagnosisHistory,
      }
      setInvestigations(upsertInvestigation(next))
      return next
    })
  }

  const clearTransientEvidence = () => {
    evidence.forEach((item) => URL.revokeObjectURL(item.previewUrl))
    setEvidence([])
    setReviewed(false)
    setIssueSlug(undefined)
  }

  const newInvestigation = () => {
    clearTransientEvidence()
    const next = createInvestigation(`Plant ${investigations.length + 1}`)
    replaceInvestigation(next)
    setContext(next.context)
    setView('diagnose')
  }

  const reopenInvestigation = (id: string) => {
    const next = activateInvestigation(id)
    if (!next || next.id === investigation.id) return
    clearTransientEvidence()
    setInvestigation(next)
    setContext(next.context)
    setView('diagnose')
  }

  const renameInvestigation = (plantName: string) => {
    const next = { ...investigation, plantName, updatedAt: new Date().toISOString() }
    replaceInvestigation(next)
  }

  const handleFiles = async (slot: EvidenceSlot, fileList: FileList) => {
    const files = [...fileList].slice(0, slot === 'close-up' ? 4 : 1)
    const additions = files.map((file) => ({ id: makeId('evidence'), file, previewUrl: URL.createObjectURL(file), slot, quality: 'checking' as const, notes: [] }))
    setReviewed(false)
    setEvidence((current) => {
      current.filter((item) => item.slot === slot).forEach((item) => URL.revokeObjectURL(item.previewUrl))
      return slot === 'close-up' ? [...current.filter((item) => item.slot !== slot), ...additions] : [...current.filter((item) => item.slot !== slot), additions[0]]
    })
    await Promise.all(additions.map(async (addition) => {
      const inspection = await inspectEvidenceFile(addition.file)
      setEvidence((current) => current.map((item) => item.id === addition.id ? { ...item, ...inspection } : item))
    }))
  }

  const removeFile = (id: string) => {
    setEvidence((current) => {
      const target = current.find((item) => item.id === id)
      if (target) URL.revokeObjectURL(target.previewUrl)
      return current.filter((item) => item.id !== id)
    })
    setReviewed(false)
  }

  const openIssue = (slug: string) => { setIssueSlug(slug); setView('issues') }

  const applyVisualObservations = (indicators: string[]) => {
    setContext((current) => {
      const next = { ...current, symptoms: [...new Set([...current.symptoms, ...indicators])] }
      syncInvestigation(next)
      return next
    })
    setReviewed(false)
  }

  const reviewEvidence = () => {
    setReviewed(true)
    const ranked = rankDifferentials(issues, context, evidence, caseHistory)
    const top = ranked[0]
    const diagnosis: DiagnosticSnapshot = {
      reviewedAt: new Date().toISOString(),
      leadingIssueSlug: top?.issue.slug,
      leadingIssueName: top?.issue.name,
      confidence: top?.confidence,
      supporting: top?.supporting ?? [],
      contradicting: top?.contradicting ?? [],
      missing: top?.missing ?? [],
      alternativeIssueSlugs: ranked.slice(1, 5).map((item) => item.issue.slug),
    }
    syncInvestigation(context, diagnosis)
  }

  const updateContext = (next: GrowContext) => { setContext(next); setReviewed(false); syncInvestigation(next) }

  return (
    <AppShell activeView={view} onViewChange={setView}>
      {view === 'diagnose' ? (
        <div className="diagnostic-page grow-doc-workspace">
          <InvestigationManager active={investigation} cases={investigations} onActivate={reopenInvestigation} onCreate={newInvestigation} onRename={renameInvestigation} />
          <section className="diagnostic-intro grow-doc-hero">
            <div><span>Evidence-guided plant health</span><h1>Document the plant before you diagnose it.</h1><p>Build a stronger plant-health case from real photos or video, crop stage, root-zone conditions, environmental measurements, recent changes, and symptom location. Grow Doc compares plausible causes; it does not pretend one image proves a diagnosis.</p></div>
            <aside className="intro-note grow-doc-hero-note"><strong>Active investigation</strong><ol><li><b>{investigation.plantName || 'Unnamed plant'}</b><span>Case {investigation.id.slice(-6)} · {caseHistory.length} follow-up{caseHistory.length === 1 ? '' : 's'}</span></li><li><b>Capture evidence</b><span>Whole plant, affected area, close detail, root zone, or short video.</span></li><li><b>Review differentials</b><span>Current evidence is compared with this case history without allowing history alone to confirm a condition.</span></li></ol></aside>
          </section>
          <div className="grow-doc-stepbar" aria-label="Diagnostic workflow"><div><span>01</span><strong>Evidence</strong><small>Photos & video</small></div><div><span>02</span><strong>Context</strong><small>Measurements & history</small></div><div><span>03</span><strong>Review</strong><small>Differentials & next checks</small></div></div>
          <div className="diagnostic-layout">
            <div className="workflow-column"><EvidenceUploader evidence={evidence} onFiles={handleFiles} onRemove={removeFile} /><VisualObservationReview evidence={evidence} selectedSymptoms={context.symptoms} onApply={applyVisualObservations} /><GrowContextForm context={context} onChange={updateContext} /></div>
            <DiagnosticResult evidence={evidence} context={context} results={results} reviewed={reviewed} caseTrend={caseTrend} onReview={reviewEvidence} onOpenIssue={openIssue} onOpenAtlas={() => setView('atlas')} onOpenReferences={() => setView('references')} />
          </div>
        </div>
      ) : null}
      {view === 'atlas' ? <LivingPlantAtlas investigation={investigation} issue={leadingIssue} /> : null}
      {view === 'issues' ? <IssueLibrary initialSlug={issueSlug} onClearInitialSlug={() => setIssueSlug(undefined)} /> : null}
      {view === 'references' ? <ReferenceLibrary onOpenIssue={openIssue} focusSlugs={referenceFocusSlugs} /> : null}
      {view === 'coverage' ? <CoverageDashboard /> : null}
      {view === 'log' ? <GrowLog investigation={investigation} onEntriesChange={() => setHistoryRevision((value) => value + 1)} /> : null}
      {view === 'about' ? <About /> : null}
    </AppShell>
  )
}
