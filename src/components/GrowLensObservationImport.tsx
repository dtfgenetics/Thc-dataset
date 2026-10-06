import { FileJson2, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { growLensImportSummary, parseGrowLensScientificObservationImport, type GrowLensImportContext } from '../lib/growlens-observation-import'

interface Props {
  onApply: (value: GrowLensImportContext) => void
}

const MAX_BYTES = 512 * 1024

export function GrowLensObservationImport({ onApply }: Props) {
  const [candidate, setCandidate] = useState<GrowLensImportContext | null>(null)
  const [fileName, setFileName] = useState('')
  const [error, setError] = useState('')

  const readFile = async (file: File | undefined) => {
    setCandidate(null)
    setError('')
    setFileName('')
    if (!file) return
    if (file.size > MAX_BYTES) {
      setError('The observation JSON is too large. Export only structured observation records; images and video are not imported here.')
      return
    }
    if (!file.name.toLowerCase().endsWith('.json') && file.type !== 'application/json') {
      setError('Choose a JSON observation export.')
      return
    }
    try {
      const value = parseGrowLensScientificObservationImport(await file.text())
      setCandidate(value)
      setFileName(file.name)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'This file could not be read as a compatible GrowLens observation export.')
    }
  }

  return (
    <section className="growlens-import" aria-labelledby="growlens-import-title">
      <div className="growlens-import__heading">
        <FileJson2 size={21} />
        <div>
          <span>Optional structured context</span>
          <h2 id="growlens-import-title">Import GrowLens measurements</h2>
          <p>Review a GrowLens scientific-observation JSON export before applying it. Images, diagnoses, and private media bytes are not transferred.</p>
          <a className="growlens-import__link" href="/growlens/">Open GrowLens →</a>
        </div>
      </div>
      <label className="growlens-import__picker">
        <span>Choose observation JSON</span>
        <input type="file" accept=".json,application/json" onChange={(event) => { void readFile(event.target.files?.[0]) }} />
      </label>
      <p className="growlens-import__status" role="status" aria-live="polite">
        {error || (candidate ? `${fileName}: ${growLensImportSummary(candidate)}` : 'No observation file selected.')}
      </p>
      {candidate ? (
        <div className="growlens-import__review">
          <div>
            <ShieldCheck size={18} />
            <p><strong>Context only.</strong> Applying these measurements does not confirm a diagnosis or raise confidence by itself.</p>
          </div>
          <dl>
            {candidate.temperatureC ? <div><dt>Temperature</dt><dd>{candidate.temperatureC} °C</dd></div> : null}
            {candidate.humidityPercent ? <div><dt>RH</dt><dd>{candidate.humidityPercent}%</dd></div> : null}
            {candidate.ppfd ? <div><dt>PPFD</dt><dd>{candidate.ppfd} µmol/m²/s</dd></div> : null}
            {candidate.dli ? <div><dt>DLI</dt><dd>{candidate.dli} mol/m²/day</dd></div> : null}
            <div><dt>Source observations</dt><dd>{candidate.sourceObservationIds.length}</dd></div>
          </dl>
          <button type="button" className="secondary-button" onClick={() => onApply(candidate)}>Apply to this investigation</button>
        </div>
      ) : null}
    </section>
  )
}
