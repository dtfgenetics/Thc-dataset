import { AlertTriangle, ArrowRight, CheckCircle2, ChevronDown, FileImage, FlaskConical, History, Leaf, Search, ShieldCheck } from 'lucide-react'
import type { CaseTrendSummary, Differential, EvidenceFile, GrowContext } from '../types'

interface DiagnosticResultProps {
  evidence: EvidenceFile[]
  context: GrowContext
  results: Differential[]
  reviewed: boolean
  caseTrend: CaseTrendSummary
  onReview: () => void
  onOpenIssue: (slug: string) => void
  onOpenAtlas: () => void
  onOpenReferences: () => void
}

const normalise = (value: string) => value.trim().toLowerCase()

function discriminatingEvidence(top: Differential, runnerUp: Differential | undefined, context: GrowContext) {
  if (!runnerUp) return []
  const selected = new Set(context.symptoms.map(normalise))
  const runnerIndicators = new Set(runnerUp.issue.indicators.map(normalise))
  const topIndicators = new Set(top.issue.indicators.map(normalise))

  const topOnly = top.issue.indicators.filter((indicator) => !selected.has(normalise(indicator)) && !runnerIndicators.has(normalise(indicator)))
  const runnerOnly = runnerUp.issue.indicators.filter((indicator) => !selected.has(normalise(indicator)) && !topIndicators.has(normalise(indicator)))

  return [
    ...topOnly.slice(0, 2).map((indicator) => `Evidence favoring ${top.issue.name}: ${indicator}`),
    ...runnerOnly.slice(0, 2).map((indicator) => `Evidence favoring ${runnerUp.issue.name}: ${indicator}`),
  ]
}

export function DiagnosticResult({ evidence, context, results, reviewed, caseTrend, onReview, onOpenIssue, onOpenAtlas, onOpenReferences }: DiagnosticResultProps) {
  const evidenceReady = evidence.length > 0 || context.symptoms.length > 0

  if (!reviewed) {
    return (
      <aside className="result-panel neutral" aria-live="polite">
        <div className="result-icon"><Search /></div>
        <span>Your result</span>
        <h2>{evidenceReady ? 'Ready for a first review' : 'Add a plant photo to begin'}</h2>
        <p>{evidenceReady ? 'Review the current evidence to compare the most plausible causes and get the safest next step.' : 'Start with one clear whole-plant or affected-area photo. Extra measurements are optional.'}</p>
        <div className="evidence-tally"><div><strong>{evidence.length}</strong><small>media</small></div><div><strong>{context.symptoms.length}</strong><small>confirmed signs</small></div><div><strong>{[context.stage, context.medium, context.ph, context.ec].filter(Boolean).length}</strong><small>extra details</small></div></div>
        <button className="primary-button" onClick={onReview} disabled={!evidenceReady}>Review this plant <ArrowRight size={18} /></button>
        <small className="result-disclaimer">Grow Doc compares evidence and reports uncertainty. Some problems still require microscopy, root-zone measurements, or laboratory confirmation.</small>
      </aside>
    )
  }

  if (!results.length) {
    return (
      <aside className="result-panel neutral" aria-live="polite">
        <div className="result-icon warning"><AlertTriangle /></div>
        <span>Screening result</span>
        <h2>We need one better clue</h2>
        <p>The current evidence does not support a responsible leading match yet. Rather than guess, use the specific next check below.</p>
        <div className="next-step-card"><strong>Best next step</strong><p>{caseTrend.recommendedNextStep}</p><small>{caseTrend.rationale}</small></div>
        <button className="secondary-button" onClick={onReview}>Review again</button>
      </aside>
    )
  }

  const top = results[0]
  const runnerUp = results[1]
  const scoreMargin = runnerUp ? top.score - runnerUp.score : undefined
  const discriminators = discriminatingEvidence(top, runnerUp, context)

  return (
    <aside className="result-panel result-ready" aria-live="polite">
      <div className="result-heading-row">
        <div className="result-icon"><FlaskConical /></div>
        <div className={`confidence confidence-${top.confidence.toLowerCase()}`}>{top.confidence} confidence</div>
      </div>
      <span>Leading possibility</span>
      <h2>{top.issue.name}</h2>
      <p>{top.issue.summary}</p>

      {top.confidence !== 'High' ? <div className="result-caution"><AlertTriangle size={18} /><div><strong>Probable, not confirmed</strong><p>A look-alike can still explain the current evidence. Avoid broad or irreversible treatment until the next check supports this direction.</p></div></div> : null}

      <section className="action-plan" aria-label="Recommended next actions">
        <div className="action-plan-heading"><ShieldCheck size={20} /><div><strong>What to do now</strong><small>Low-risk steps supported by the current profile</small></div></div>
        <ol>{top.issue.immediateActions.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ol>
        {top.issue.correctivePlan.length ? <div className="corrective-preview"><strong>Corrective direction</strong><ul>{top.issue.correctivePlan.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
        {top.issue.warnings.length ? <div className="avoid-preview"><strong>Avoid for now</strong><p>{top.issue.warnings.slice(0, 2).join(' · ')}</p></div> : null}
      </section>

      <div className="next-step-card"><strong>Best next check</strong><p>{caseTrend.recommendedNextStep}</p><small>{caseTrend.rationale}</small></div>

      {results.length > 1 ? (
        <div className="other-results compact-results">
          <strong>Other realistic possibilities</strong>
          {results.slice(1, 3).map((item) => <button key={item.issue.id} onClick={() => onOpenIssue(item.issue.slug)}><span>{item.issue.name}</span><small>{item.confidence} confidence{item.supporting[0] ? ` · ${item.supporting[0]}` : ''}</small></button>)}
        </div>
      ) : null}

      <details className="technical-details">
        <summary><span><strong>Why Grow Doc ranked this result</strong><small>Evidence, contradictions, and missing confirmation</small></span><ChevronDown size={18} /></summary>
        <div className="technical-details-body">
          <div className="evidence-list positive"><strong><CheckCircle2 size={17} /> Supporting evidence</strong>{top.supporting.length ? <ul>{top.supporting.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No symptom-level support recorded.</p>}</div>
          {top.contextSignals?.length ? <div className="evidence-list"><strong><CheckCircle2 size={17} /> Context used</strong><ul>{top.contextSignals.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
          {top.historySignals?.length ? <div className="evidence-list positive"><strong><History size={17} /> Case history</strong><ul>{top.historySignals.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
          {caseTrend.changes.length ? <div className="evidence-list"><strong><History size={17} /> What changed</strong><ul>{caseTrend.changes.map((item) => <li key={item}>{item}</li>)}</ul><small>Overall case trend: {caseTrend.trend}.</small></div> : null}
          {top.contradicting.length ? <div className="evidence-list negative"><strong><AlertTriangle size={17} /> Evidence against</strong><ul>{top.contradicting.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
          {runnerUp ? <div className="missing-evidence"><strong>Why this ranks above {runnerUp.issue.name}</strong><p>{top.issue.name} currently leads by {scoreMargin?.toFixed(1)} ranking points. A small margin means the order can change when better evidence is added.</p></div> : null}
          {discriminators.length ? <div className="evidence-list"><strong><Search size={17} /> Best evidence to separate the top two</strong><ul>{discriminators.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
          <div className="missing-evidence"><strong>What would improve confidence</strong><p>{top.missing.slice(0, 4).join(' · ') || 'No additional structured fields required'}</p></div>
        </div>
      </details>

      <div className="diagnostic-actions">
        <button className="primary-button" onClick={() => onOpenIssue(top.issue.slug)}>Open full guide <ArrowRight size={18} /></button>
        <button className="secondary-button" onClick={onOpenReferences}><FileImage size={17} /> Compare references</button>
        <button className="secondary-button" onClick={onOpenAtlas}><Leaf size={17} /> Plant anatomy</button>
      </div>
    </aside>
  )
}
