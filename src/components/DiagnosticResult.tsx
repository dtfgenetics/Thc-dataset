import { AlertTriangle, ArrowRight, CheckCircle2, FlaskConical, Search } from 'lucide-react'
import type { Differential, EvidenceFile, GrowContext } from '../types'

interface DiagnosticResultProps {
  evidence: EvidenceFile[]
  context: GrowContext
  results: Differential[]
  reviewed: boolean
  onReview: () => void
  onOpenIssue: (slug: string) => void
}

export function DiagnosticResult({ evidence, context, results, reviewed, onReview, onOpenIssue }: DiagnosticResultProps) {
  const evidenceReady = evidence.length > 0 || context.symptoms.length > 0

  if (!reviewed) {
    return (
      <aside className="result-panel neutral" aria-live="polite">
        <div className="result-icon"><Search /></div>
        <span>Evidence summary</span>
        <h2>{evidenceReady ? 'Ready to review evidence' : 'Not enough evidence yet'}</h2>
        <p>{evidenceReady ? 'Review the submitted media and context to produce a ranked differential—not a guaranteed diagnosis.' : 'Add at least one clear image or select confirmed symptoms to begin.'}</p>
        <div className="evidence-tally">
          <div><strong>{evidence.length}</strong><small>media files</small></div>
          <div><strong>{context.symptoms.length}</strong><small>symptoms</small></div>
          <div><strong>{[context.stage, context.medium, context.ph, context.ec].filter(Boolean).length}</strong><small>context fields</small></div>
        </div>
        <button className="primary-button" onClick={onReview} disabled={!evidenceReady}>Review evidence <ArrowRight size={18} /></button>
        <small className="result-disclaimer">The current build ranks structured symptom evidence. Pixel-model analysis is not yet connected and is never implied.</small>
      </aside>
    )
  }

  if (!results.length) {
    return (
      <aside className="result-panel neutral" aria-live="polite">
        <div className="result-icon warning"><AlertTriangle /></div>
        <span>Screening result</span>
        <h2>No defensible match yet</h2>
        <p>The evidence does not support a ranked condition. Add closer views, underside or root photos, and measured grow details.</p>
        <button className="secondary-button" onClick={onReview}>Review again</button>
      </aside>
    )
  }

  const top = results[0]
  return (
    <aside className="result-panel result-ready" aria-live="polite">
      <div className="result-icon"><FlaskConical /></div>
      <span>Ranked differential</span>
      <div className={`confidence confidence-${top.confidence.toLowerCase()}`}>{top.confidence} evidence match</div>
      <h2>{top.issue.name}</h2>
      <p>{top.issue.summary}</p>
      <div className="evidence-list positive"><strong><CheckCircle2 size={17} /> Supporting evidence</strong>{top.supporting.length ? <ul>{top.supporting.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No symptom-level support recorded.</p>}</div>
      {top.contradicting.length ? <div className="evidence-list negative"><strong><AlertTriangle size={17} /> Evidence against</strong><ul>{top.contradicting.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
      <div className="missing-evidence"><strong>What would improve this result</strong><p>{top.missing.slice(0, 3).join(' · ') || 'No additional structured fields required'}</p></div>
      <button className="primary-button" onClick={() => onOpenIssue(top.issue.slug)}>Open full issue guide <ArrowRight size={18} /></button>
      {results.length > 1 ? <div className="other-results"><strong>Other realistic possibilities</strong>{results.slice(1).map((item) => <button key={item.issue.id} onClick={() => onOpenIssue(item.issue.slug)}><span>{item.issue.name}</span><small>{item.confidence}</small></button>)}</div> : null}
    </aside>
  )
}
