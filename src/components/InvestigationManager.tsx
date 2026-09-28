import { Download, FolderOpen, Plus } from 'lucide-react'
import type { InvestigationCase } from '../types'
import { investigationExportFilename, serializeInvestigationExport } from '../lib/investigations'
import './InvestigationManager.css'

interface InvestigationManagerProps {
  active: InvestigationCase
  cases: InvestigationCase[]
  onActivate: (id: string) => void
  onCreate: () => void
  onRename: (name: string) => void
}

export function InvestigationManager({ active, cases, onActivate, onCreate, onRename }: InvestigationManagerProps) {
  const exportActiveCase = () => {
    const blob = new Blob([serializeInvestigationExport(active)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = investigationExportFilename(active)
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="investigation-manager" aria-label="Grow Doc investigations">
      <div className="investigation-manager-heading">
        <div><span>Case management</span><strong>{cases.length} saved investigation{cases.length === 1 ? '' : 's'}</strong></div>
        <div className="investigation-manager-actions"><button className="secondary-button" type="button" onClick={exportActiveCase}><Download size={16} /> Export case</button><button className="secondary-button" type="button" onClick={onCreate}><Plus size={16} /> New case</button></div>
      </div>
      <div className="investigation-manager-controls">
        <label>
          Active plant or run
          <input value={active.plantName} onChange={(event) => onRename(event.target.value)} aria-label="Active plant or run name" />
        </label>
        <label>
          Reopen investigation
          <div className="investigation-select-wrap"><FolderOpen size={16} /><select value={active.id} onChange={(event) => onActivate(event.target.value)}>{cases.map((item) => <option key={item.id} value={item.id}>{item.plantName || 'Unnamed plant'} · {new Date(item.updatedAt).toLocaleDateString()}</option>)}</select></div>
        </label>
      </div>
      {active.diagnosisHistory?.length ? (
        <div className="investigation-timeline">
          <strong>Diagnosis timeline</strong>
          {active.diagnosisHistory.slice().reverse().slice(0, 6).map((snapshot) => (
            <article key={`${snapshot.reviewedAt}-${snapshot.leadingIssueSlug ?? 'none'}`}>
              <time>{new Date(snapshot.reviewedAt).toLocaleString()}</time>
              <span>{snapshot.leadingIssueName ?? 'No defensible match'}</span>
              <small>{snapshot.confidence ? `${snapshot.confidence} evidence match` : 'Insufficient evidence'}{snapshot.alternativeIssueSlugs.length ? ` · ${snapshot.alternativeIssueSlugs.length} alternative${snapshot.alternativeIssueSlugs.length === 1 ? '' : 's'}` : ''}</small>
            </article>
          ))}
        </div>
      ) : <p className="investigation-manager-empty">This case has no saved diagnostic reviews yet.</p>}
    </section>
  )
}
