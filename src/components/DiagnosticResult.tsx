import { AlertTriangle, ArrowRight, CheckCircle2, FileImage, FlaskConical, History, Leaf, Search } from 'lucide-react'
import type { Differential, EvidenceFile, GrowContext } from '../types'

interface DiagnosticResultProps {
  evidence: EvidenceFile[]
  context: GrowContext
  results: Differential[]
  reviewed: boolean
  onReview: () => void
  onOpenIssue: (slug: string) => void
  onOpenAtlas: () => void
  onOpenReferences: () => void
}

export function DiagnosticResult({ evidence, context, results, reviewed, onReview, onOpenIssue, onOpenAtlas, onOpenReferences }: DiagnosticResultProps) {
  const evidenceReady = evidence.length > 0 || context.symptoms.length > 0

  if (!reviewed) {
    return <aside className="result-panel neutral" aria-live="polite"><div className="result-icon"><Search /></div><span>Evidence summary</span><h2>{evidenceReady ? 'Ready to review evidence' : 'Not enough evidence yet'}</h2><p>{evidenceReady ? 'Review current media, measurements, symptoms, and saved follow-up history to produce a ranked differential—not a guaranteed diagnosis.' : 'Add at least one clear image or select confirmed symptoms to begin.'}</p><div className="evidence-tally"><div><strong>{evidence.length}</strong><small>media files</small></div><div><strong>{context.symptoms.length}</strong><small>symptoms</small></div><div><strong>{[context.stage, context.medium, context.ph, context.ec].filter(Boolean).length}</strong><small>context fields</small></div></div><button className="primary-button" onClick={onReview} disabled={!evidenceReady}>Review evidence <ArrowRight size={18} /></button><small className="result-disclaimer">History may re-rank plausible causes, but it cannot independently confirm a condition or bypass required visual, microscopic, root-zone, or laboratory evidence.</small></aside>
  }

  if (!results.length) {
    return <aside className="result-panel neutral" aria-live="polite"><div className="result-icon warning"><AlertTriangle /></div><span>Screening result</span><h2>No defensible match yet</h2><p>The combined current and historical evidence does not support a ranked condition. Add closer views, underside or root photos, and measured grow details rather than guessing from one symptom.</p><button className="secondary-button" onClick={onReview}>Review again</button></aside>
  }

  const top = results[0]
  const nextCheck = top.issue.confirmation[0] ?? 'Gather another discriminating observation before making a corrective change.'

  return (
    <aside className="result-panel result-ready" aria-live="polite">
      <div className="result-icon"><FlaskConical /></div><span>Ranked differential</span><div className={`confidence confidence-${top.confidence.toLowerCase()}`}>{top.confidence} evidence match</div><h2>{top.issue.name}</h2><p>{top.issue.summary}</p>
      {top.confidence !== 'High' ? <div className="missing-evidence"><strong>Leading hypothesis—not confirmation</strong><p>Another condition can still explain the current evidence. Verify the discriminating evidence below before making an irreversible or broad correction.</p></div> : null}
      <div className="evidence-list positive"><strong><CheckCircle2 size={17} /> Supporting evidence</strong>{top.supporting.length ? <ul>{top.supporting.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No symptom-level support recorded.</p>}</div>
      {top.historySignals?.length ? <div className="evidence-list positive"><strong><History size={17} /> Longitudinal evidence</strong><ul>{top.historySignals.map((item) => <li key={item}>{item}</li>)}</ul><small>Historical signals are intentionally bounded and cannot establish high confidence by themselves.</small></div> : null}
      {top.contradicting.length ? <div className="evidence-list negative"><strong><AlertTriangle size={17} /> Evidence against</strong><ul>{top.contradicting.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
      <div className="missing-evidence"><strong>What would improve this result</strong><p>{top.missing.slice(0, 4).join(' · ') || 'No additional structured fields required'}</p></div>
      <div className="missing-evidence"><strong>Next check before correction</strong><p>{nextCheck}</p></div>
      <div className="diagnostic-actions"><button className="primary-button" onClick={() => onOpenIssue(top.issue.slug)}>Open full issue guide <ArrowRight size={18} /></button><button className="secondary-button" onClick={onOpenAtlas}><Leaf size={17} /> Inspect relevant anatomy</button><button className="secondary-button" onClick={onOpenReferences}><FileImage size={17} /> Compare reference evidence</button></div>
      {results.length > 1 ? <div className="other-results"><strong>Other realistic possibilities</strong>{results.slice(1).map((item) => <button key={item.issue.id} onClick={() => onOpenIssue(item.issue.slug)}><span>{item.issue.name}</span><small>{item.confidence} · {item.supporting.length} supporting signal{item.supporting.length === 1 ? '' : 's'}{item.historySignals?.length ? ` · ${item.historySignals.length} history signal${item.historySignals.length === 1 ? '' : 's'}` : ''}{item.supporting[0] ? ` · ${item.supporting[0]}` : ''}</small></button>)}</div> : null}
    </aside>
  )
}
