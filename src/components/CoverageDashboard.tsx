import { AlertTriangle, CheckCircle2, Database, FileImage, ShieldCheck } from 'lucide-react'
import { categoryOrder, issues } from '../data/issues'
import { hasResolvedDisplayMedia, isDisplayableMedia } from '../lib/media'

const targetByCategory: Partial<Record<(typeof categoryOrder)[number], number>> = {
  'Nutrient deficiency': 144,
  'Nutrient toxicity': 120,
  Insect: 105,
  Mite: 90,
  'Fungal pathogen': 105,
  'Bacterial pathogen': 45,
  'Root pathogen': 60,
  Viroid: 30,
  Virus: 30,
  'Phytoplasma / Spiroplasma': 15,
  'Genetic / developmental': 72,
  'Environmental stress': 70,
  'Water / root-zone': 60,
  'Normal development': 25,
  'Insufficient evidence': 125,
}

export function CoverageDashboard() {
  const approvedReferenceMedia = issues.flatMap((issue) => issue.media).filter(isDisplayableMedia)
  const currentImages = approvedReferenceMedia.length
  const profilesWithVisualReferences = issues.filter((issue) => hasResolvedDisplayMedia(issue, issues)).length
  const sourced = issues.filter((issue) => issue.sources.length > 0).length
  const reviewed = issues.filter((issue) => issue.reviewStatus === 'reviewed').length
  const totalTarget = Object.values(targetByCategory).reduce((sum, value) => sum + (value ?? 0), 0)

  return (
    <div className="view-container coverage-view">
      <div className="view-intro"><div><span>Dataset health</span><h1>Coverage dashboard</h1><p>Transparent counts for records, unique approved assets, issue-page visual coverage, sources, and scientific review status.</p></div></div>
      <div className="coverage-summary"><Summary icon={<Database />} value={issues.length} label="structured conditions" /><Summary icon={<FileImage />} value={currentImages} label="unique approved images" warning={!currentImages} /><Summary icon={<FileImage />} value={profilesWithVisualReferences} label="profiles with visual refs" warning={profilesWithVisualReferences < issues.length} /><Summary icon={<ShieldCheck />} value={reviewed} label="reviewed records" /><Summary icon={<CheckCircle2 />} value={sourced} label="records with sources" /></div>
      <section className="coverage-table-wrap"><div className="coverage-table-heading"><div><h2>Image collection plan</h2><p>Unique asset counts never duplicate a verified file just because one licensed composite contains several diagnosis classes. “Profiles with visual refs” includes safe shared-composite display links.</p></div><span>{currentImages} unique assets / {totalTarget} collection target</span></div><div className="coverage-table" role="table" aria-label="Dataset image coverage by category"><div className="coverage-row header" role="row"><span>Category</span><span>Records</span><span>Unique assets</span><span>Profiles with visual refs</span><span>Initial target</span><span>Asset coverage</span></div>{categoryOrder.map((category) => { const categoryIssues = issues.filter((issue) => issue.category === category); const imageCount = categoryIssues.flatMap((issue) => issue.media).filter(isDisplayableMedia).length; const profilesWithRefs = categoryIssues.filter((issue) => hasResolvedDisplayMedia(issue, issues)).length; const target = targetByCategory[category] ?? 0; const percent = target ? Math.min(100, Math.round((imageCount / target) * 100)) : 0; return <div className="coverage-row" role="row" key={category}><strong>{category}</strong><span>{categoryIssues.length}</span><span>{imageCount}</span><span>{profilesWithRefs} / {categoryIssues.length}</span><span>{target}</span><div className="coverage-progress"><i style={{ width: `${percent}%` }} /><small>{percent}%</small></div></div>})}</div></section>
      <section className="qa-panel"><AlertTriangle /><div><h2>Build-blocking data rules</h2><ul><li>Reviewed conditions require mapped sources.</li><li>Approved media requires creator, license, source, condition, view, and confirmation metadata.</li><li>A shared composite is stored once; linked issue pages may display it only when the source explicitly identifies that condition in a bounded panel or column.</li><li>Shared full composites remain reference-only until panels are independently cropped, reviewed, hashed, and split safely.</li><li>Training and evaluation splits must not overlap.</li><li>Viroid and virus pages must state that visual evidence cannot confirm infection.</li><li>User uploads are excluded from training unless separately consented to and reviewed.</li></ul></div></section>
    </div>
  )
}

function Summary({ icon, value, label, warning = false }: { icon: React.ReactNode; value: number; label: string; warning?: boolean }) {
  return <div className={warning ? 'summary warning' : 'summary'}><span>{icon}</span><strong>{value.toLocaleString()}</strong><small>{label}</small></div>
}
