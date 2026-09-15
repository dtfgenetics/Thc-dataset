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
  const caseHistory = useMemo(
    () => loadLogEntries().filter((entry) => entry.investigationId === investigation.id),
    [investigation.id, historyRevision],
  )
  const results = useMemo(
    () => reviewed ? rankDifferentials(issues, context, evidence, caseHistory) : [],
    [context, evidence, reviewed, caseHistory],
  )
  const caseTrend = useMemo(() => summarizeCaseTrend(context, caseHistory, results), [context, caseHistory, results])

  const replaceInvestigation = (next: InvestigationCase) => {
    setInvestigation(next)
    setInvestigations(upsertInvestigation(next))
  }

  const syncContext = (nextContext: GrowContext) => {
    setContext(nextContext)
    setReviewed(false)
    setInvestigation((current) => {
      const next = { ...current, context: nextContext, updatedAt: new Date().toISOString() }
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
    replaceInvestigation({ ...investigation, plantName, updatedAt: new Date().toISOString() })
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
    syncContext({ ...context, symptoms: [...new Set([...context.symptoms, ...indicators])] })
  }

  const reviewEvidence = () => {
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

    setReviewed(true)
    setInvestigation((current) => {
      const next: InvestigationCase = {
        ...current,
        updatedAt: new Date().toISOString(),
        context,
        evidenceSummary: evidence.map((item) => ({ slot: item.slot, quality: item.quality, notes: item.notes })),
        diagnosis,
        diagnosisHistory: [...(current.diagnosisHistory ?? []), diagnosis].slice(-30),
      }
      setInvestigations(upsertInvestigation(next))
      return next
    })
  }

  return (
    <AppShell activeView={view} onViewChange={setView}>
      {view === 'diagnose' ? (
        <div className="diagnostic-page grow-doc-workspace">
          <InvestigationManager active={investigation} cases={investigations} onActivate={reopenInvestigation} onCreate={newInvestigation} onRename={renameInvestigation} />

          <section className="diagnostic-intro grow-doc-hero">
            <div className="hero-copy">
              <h1>Show us the plant. Get a clear next step.</h1>
              <p>
                Start with a clear photo. Grow Doc compares visible symptoms with reviewed plant-health evidence,
                then shows the leading possibilities, what to check next, and what actions are safest at the current confidence level.
              </p>
            </div>
            <aside className="grow-doc-hero-note" aria-label="How to start">
              <strong>Start here</strong>
              <ol>
                <li><b>Add one clear photo</b><span>A whole-plant or affected-area view is enough to begin.</span></li>
                <li><b>Review visible signs</b><span>Confirm only observations you can actually see.</span></li>
                <li><b>Act on the result</b><span>Use the next check and low-risk corrective steps before broad treatment.</span></li>
              </ol>
            </aside>
          </section>

          <div className="grow-doc-stepbar" aria-label="Diagnostic workflow">
            <div><span>01</span><strong>Upload</strong><small>Start with the plant</small></div>
            <div><span>02</span><strong>Review</strong><small>Confirm visible signs</small></div>
            <div><span>03</span><strong>Act</strong><small>Get the next step</small></div>
          </div>

          <div className="diagnostic-layout">
            <div className="workflow-column">
              <EvidenceUploader evidence={evidence} onFiles={handleFiles} onRemove={removeFile} />
              <VisualObservationReview evidence={evidence} selectedSymptoms={context.symptoms} onApply={applyVisualObservations} />
              <GrowContextForm context={context} onChange={syncContext} />
            </div>
            <DiagnosticResult
              evidence={evidence}
              context={context}
              results={results}
              reviewed={reviewed}
              caseTrend={caseTrend}
              onReview={reviewEvidence}
              onOpenIssue={openIssue}
              onOpenAtlas={() => setView('atlas')}
              onOpenReferences={() => setView('references')}
            />
          </div>
        </div>
      ) : null}
      {view === 'atlas' ? <LivingPlantAtlas /> : null}
      {view === 'issues' ? <IssueLibrary initialSlug={issueSlug} onClearInitialSlug={() => setIssueSlug(undefined)} /> : null}
      {view === 'references' ? <ReferenceLibrary onOpenIssue={openIssue} /> : null}
      {view === 'coverage' ? <CoverageDashboard /> : null}
      {view === 'log' ? <GrowLog investigation={investigation} onEntriesChange={() => setHistoryRevision((value) => value + 1)} /> : null}
      {view === 'about' ? <About /> : null}
    </AppShell>
  )
}
