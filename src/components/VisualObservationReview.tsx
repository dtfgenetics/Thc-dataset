import { AlertTriangle, Check, Eye, LoaderCircle, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { symptomOptions } from '../data/issues'
import { requestVisualObservations, type VisualObservationResult } from '../lib/visual-observations'
import type { EvidenceFile } from '../types'

interface VisualObservationReviewProps {
  evidence: EvidenceFile[]
  selectedSymptoms: string[]
  onApply: (indicators: string[]) => void
}

export function VisualObservationReview({ evidence, selectedSymptoms, onApply }: VisualObservationReviewProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<VisualObservationResult | null>(null)
  const [approved, setApproved] = useState<string[]>([])

  const pendingIndicators = useMemo(
    () => result?.matchedIndicators.filter((indicator) => !selectedSymptoms.includes(indicator)) ?? [],
    [result, selectedSymptoms],
  )

  const analyze = async () => {
    setLoading(true)
    setError('')
    setApproved([])
    try {
      const next = await requestVisualObservations(evidence, symptomOptions)
      setResult(next)
    } catch (analysisError) {
      setResult(null)
      setError(analysisError instanceof Error ? analysisError.message : 'Visual analysis could not be completed.')
    } finally {
      setLoading(false)
    }
  }

  const toggle = (indicator: string) => {
    setApproved((current) => current.includes(indicator) ? current.filter((item) => item !== indicator) : [...current, indicator])
  }

  const apply = () => {
    if (!approved.length) return
    onApply(approved)
    setApproved([])
  }

  return (
    <section className="visual-observation-section" aria-labelledby="visual-observation-title">
      <div className="section-heading compact">
        <div><span>Optional</span><h2 id="visual-observation-title">Review visual observations</h2></div>
        <p>AI may suggest visible signs from uploaded media. You decide which observations are accurate before they affect the differential.</p>
      </div>

      <div className="visual-observation-card">
        <div className="visual-observation-intro">
          <Eye />
          <div>
            <strong>Observation assistant—not a diagnosis model</strong>
            <p>It cannot confirm nutrient disorders, pathogens, viroids, viruses, root disease, or microscopic pests from appearance alone.</p>
          </div>
        </div>

        <button className="secondary-button visual-analyze-button" type="button" onClick={analyze} disabled={!evidence.length || loading}>
          {loading ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
          {loading ? 'Analyzing visible features…' : result ? 'Analyze media again' : 'Analyze uploaded media'}
        </button>

        {!evidence.length ? <small>Add an image or video first. Manual symptom selection remains available below.</small> : null}
        {error ? <div className="visual-observation-error"><AlertTriangle size={17} /><span>{error}</span></div> : null}

        {result ? (
          <div className="visual-observation-result">
            <div className="visual-observation-summary">
              <strong>Model observation summary</strong>
              <p>{result.summary || 'No reliable summary was returned.'}</p>
              <small>{result.provider} · {result.model}</small>
            </div>

            {result.unknownOrOutOfScope ? (
              <div className="visual-observation-warning"><AlertTriangle size={17} /><span>The media did not provide enough reliable plant-symptom evidence for confident visual observations.</span></div>
            ) : null}

            {pendingIndicators.length ? (
              <div className="visual-indicator-review">
                <strong>Suggested visible symptoms — select only what you agree with</strong>
                <div className="visual-indicator-list">
                  {pendingIndicators.map((indicator) => (
                    <button type="button" key={indicator} className={approved.includes(indicator) ? 'approved' : ''} onClick={() => toggle(indicator)}>
                      {approved.includes(indicator) ? <Check size={15} /> : null}
                      {indicator}
                    </button>
                  ))}
                </div>
                <button className="primary-button" type="button" disabled={!approved.length} onClick={apply}>Add selected observations</button>
              </div>
            ) : (
              <p className="visual-observation-empty">No new controlled symptom indicators were suggested. Use the visible-feature notes and manual symptom picker instead.</p>
            )}

            {result.visibleFeatures.length ? (
              <div className="visual-feature-list">
                <strong>Other visible features</strong>
                <ul>{result.visibleFeatures.map((feature, index) => <li key={`${feature.observation}-${index}`}><span>{feature.confidence}</span>{feature.observation}</li>)}</ul>
              </div>
            ) : null}

            {result.qualityNotes.length ? <p className="visual-observation-notes"><strong>Image quality:</strong> {result.qualityNotes.join(' · ')}</p> : null}
            {result.suggestedNextViews.length ? <p className="visual-observation-notes"><strong>Helpful next views:</strong> {result.suggestedNextViews.join(' · ')}</p> : null}
            {result.uncertainFeatures.length ? <p className="visual-observation-notes"><strong>Uncertain:</strong> {result.uncertainFeatures.join(' · ')}</p> : null}
            {result.providerDataUseNotice ? <small className="provider-data-notice">{result.providerDataUseNotice}</small> : null}
          </div>
        ) : null}
      </div>
    </section>
  )
}
