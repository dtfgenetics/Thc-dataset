import { ExternalLink, FileImage, Search } from 'lucide-react'
import { useDeferredValue, useMemo, useState } from 'react'
import { issues } from '../data/catalog'
import { resolvedDisplayMediaForIssue } from '../lib/media'
import { referenceMediaSources } from '../lib/reference-media-assets'
import { ImagePlaceholder } from './icons'
import { ResilientImage } from './ResilientImage'

const references = issues.flatMap((issue) => resolvedDisplayMediaForIssue(issue, issues)
  .filter(({ media }) => media.url || media.thumbnailUrl)
  .map((reference) => ({ issue, ...reference })))
const issuesWithDisplayableReferences = new Set(references.map(({ issue }) => issue.slug))
const referenceCoverage = {
  total: issues.length,
  withReference: issuesWithDisplayableReferences.size,
  withoutReference: issues.length - issuesWithDisplayableReferences.size,
}
const categories = [...new Set(references.map(({ issue }) => issue.category))].sort()
const views = [...new Set(references.map(({ media }) => media.view).filter(Boolean))].sort()
const hostLabels = { cannabis: 'Cannabis plant context', 'non-cannabis': 'Other plant context', 'organism-only': 'Organism only' }

export function ReferenceLibrary({ onOpenIssue }: { onOpenIssue: (slug: string) => void }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All')
  const [host, setHost] = useState('All')
  const [view, setView] = useState('All')
  const deferredQuery = useDeferredValue(query)
  const filtered = useMemo(() => {
    const needle = deferredQuery.trim().toLowerCase()
    return references.filter(({ issue, media }) => (category === 'All' || issue.category === category)
      && (host === 'All' || media.hostContext === host)
      && (view === 'All' || media.view === view)
      && [issue.name, issue.scientificName, issue.category, media.alt, media.caption, media.stage, media.view, media.creator, media.hostSpecies]
        .filter(Boolean).join(' ').toLowerCase().includes(needle))
  }, [category, host, view, deferredQuery])
  const assetCount = new Set(filtered.map(({ media }) => media.sha256 ?? media.id)).size
  const reset = () => { setQuery(''); setCategory('All'); setHost('All'); setView('All') }

  return (
    <div className="view-container references-view">
      <div className="view-intro"><div><span>Licensed visual references</span><h1>Reference images</h1><p>Compare symptoms by condition, plant context, and view. Shared figures may support several guides; their crops are references from the same source, not independent samples.</p></div><div className="library-count"><strong>{assetCount}</strong><small>distinct source assets</small></div></div>
      <section className="reference-coverage" aria-labelledby="reference-coverage-heading">
        <h2 id="reference-coverage-heading">Visual evidence coverage</h2>
        <p>{referenceCoverage.withReference} of {referenceCoverage.total} condition guides currently have at least one approved, displayable visual reference; {referenceCoverage.withoutReference} do not.</p>
        <p>Coverage is not diagnostic accuracy: a shared figure may appear in multiple guides, and a non-Cannabis or organism-only image is not proof of the condition in Cannabis. Counts reflect approved display links, not unique verified clinical cases or training examples.</p>
      </section>
      <div className="reference-discovery">
        <label className="search-field"><Search size={19} /><input aria-label="Search reference images" placeholder="Search condition, species, stage, or view" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
        <label>Condition category<select value={category} onChange={(e) => setCategory(e.target.value)}><option value="All">All categories</option>{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Plant context<select value={host} onChange={(e) => setHost(e.target.value)}><option value="All">All contexts</option>{Object.entries(hostLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Image viewpoint<select value={view} onChange={(e) => setView(e.target.value)}><option value="All">All viewpoints</option>{views.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      </div>
      <p className="reference-results" role="status">{filtered.length} guide-linked references from {assetCount} distinct source assets</p>
      {filtered.length ? <div className="reference-grid">{filtered.map(({ issue, media, shared }) => <figure key={`${media.id}-${issue.slug}`}>
        <ResilientImage sources={referenceMediaSources(media, issue.slug)} alt={shared ? `${issue.name} reference from a shared multi-condition source figure` : media.alt} fallback={<ImagePlaceholder label={`Licensed reference image unavailable for ${issue.name}`} />} />
        <figcaption><span>{issue.category}</span><h2>{issue.name}</h2><strong className="reference-context">{hostLabels[media.hostContext]}{shared ? ' · Shared figure' : ''}</strong><p>{shared ? `This source figure also documents ${issue.name}. The preview uses a condition-specific crop when available; the original figure contains other diagnoses.` : media.caption}</p>
          <dl><div><dt>View</dt><dd>{media.view}</dd></div><div><dt>Stage</dt><dd>{media.stage}</dd></div><div><dt>Confirmation</dt><dd>{media.confirmation}</dd></div><div><dt>License</dt><dd>{media.license ?? 'Missing'}</dd></div></dl>
          <details className="reference-evidence"><summary>Attribution and interpretation limits</summary>{shared ? <p>Original figure caption: {media.caption}</p> : null}<p>{media.requiredAttribution || media.creator}</p>{shared ? <p>Use only the diagnosis-specific panel identified by the source. The complete figure contains multiple conditions.</p> : null}<ul>{media.useLimitations.map((limit) => <li key={limit}>{limit}</li>)}</ul><p>{media.trainingEligible ? 'Training eligibility is recorded for this asset; retain its documented scope and split.' : 'Reference display only. This asset is not admitted for automated training.'}</p></details>
          <div><button onClick={() => onOpenIssue(issue.slug)}>Open {issue.name} guide</button>{media.sourceUrl ? <a href={media.sourceUrl} target="_blank" rel="noreferrer">Source <ExternalLink size={14} /></a> : null}</div>
        </figcaption></figure>)}</div> : <div className="empty-state"><Search /><h2>No matching reference images</h2><p>Try a broader term or clear the category, plant-context, and viewpoint filters.</p><button onClick={reset}>Clear reference filters</button></div>}
      <section className="license-rules"><FileImage /><div><h2>Read the image in context</h2><p>A licensed image can support comparison without proving the diagnosis in your plant. Organism-only and other-plant references do not establish Cannabis injury; check the guide’s exclusions and confirmation steps.</p></div></section>
    </div>
  )
}
