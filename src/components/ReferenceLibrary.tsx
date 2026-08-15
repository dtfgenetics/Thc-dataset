import { ExternalLink, FileImage, ImageOff, Search } from 'lucide-react'
import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { issues } from '../data/issues'
import { isDisplayableMedia } from '../lib/media'
import { loadReferenceImageIndex, searchReferenceImageIndex, type ReferenceImageRecord } from '../lib/referenceData'
import type { IssueRecord, MediaRecord } from '../types'
import { ImagePlaceholder } from './icons'

export function buildReferenceSearchText(issue: IssueRecord, media: MediaRecord) {
  const sourceText = issue.sources
    .map((source) => [
      source.title,
      source.organization,
      source.url,
      source.doi,
      source.publisher,
      source.authors?.join(' '),
      source.supportedClaims.join(' '),
    ].join(' '))
    .join(' ')

  return [
    issue.name,
    issue.category,
    issue.summary,
    issue.indicators.join(' '),
    sourceText,
    media.caption,
    media.alt,
    media.diagnosticLabel,
    media.creator,
    media.license,
    media.sourceUrl,
    media.requiredAttribution,
    media.url,
    media.thumbnailUrl,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

export function ReferenceLibrary({ onOpenIssue }: { onOpenIssue: (slug: string) => void }) {
  const [query, setQuery] = useState('')
  const [datasetIndex, setDatasetIndex] = useState<ReferenceImageRecord[]>([])
  const deferredQuery = useDeferredValue(query)
  const approvedMedia = issues.flatMap((issue) => issue.media.map((media) => ({ issue, media }))).filter(({ media }) => isDisplayableMedia(media) && (media.url || media.thumbnailUrl))

  useEffect(() => {
    let isActive = true
    loadReferenceImageIndex()
      .then((records) => {
        if (isActive) setDatasetIndex(records)
      })
      .catch(() => {
        if (isActive) setDatasetIndex([])
      })
    return () => {
      isActive = false
    }
  }, [])

  const datasetMatchCount = useMemo(() => (deferredQuery ? searchReferenceImageIndex(datasetIndex, deferredQuery).length : 0), [datasetIndex, deferredQuery])
  const filtered = useMemo(() => approvedMedia.filter(({ issue, media }) => buildReferenceSearchText(issue, media).includes(deferredQuery.toLowerCase())), [approvedMedia, deferredQuery])

  return (
    <div className="view-container references-view">
      <div className="view-intro"><div><span>Licensed media only</span><h1>Reference images</h1><p>Every visible asset must carry its condition, source, allowed-use license, view, and confirmation method.</p></div><div className="library-count"><strong>{approvedMedia.length}</strong><small>approved images</small></div></div>
      <label className="search-field reference-search"><Search size={19} /><input aria-label="Search reference images" placeholder="Search by issue or category" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
      {deferredQuery && datasetMatchCount > 0 ? (
        <div className="reference-index-note"><strong>{datasetMatchCount} indexed reference matches</strong><span>Connected to the generated dataset catalog at /reference-image-index.json.</span></div>
      ) : null}
      {filtered.length ? <div className="reference-grid">{filtered.map(({ issue, media }) => <figure key={media.id}><img src={media.thumbnailUrl ?? media.url} alt={media.alt} /><figcaption><span>{issue.category}</span><h2>{issue.name}</h2><p>{media.caption}</p><dl><div><dt>Confirmation</dt><dd>{media.confirmation}</dd></div><div><dt>License</dt><dd>{media.license ?? 'Missing'}</dd></div><div><dt>View</dt><dd>{media.view}</dd></div></dl><div><button onClick={() => onOpenIssue(issue.slug)}>Open guide</button>{media.sourceUrl ? <a href={media.sourceUrl} target="_blank" rel="noreferrer">Source <ExternalLink size={14} /></a> : null}</div></figcaption></figure>)}</div> : <div className="media-empty"><ImagePlaceholder label="Reference image library awaiting reviewed media" /><div><ImageOff /><h2>No approved photographs yet</h2><p>The previous site counted text descriptions as reference records. This rebuild counts only actual media with usable licensing and scientific review metadata.</p><strong>Next content milestone: 1,096 reviewed images</strong></div></div>}
      <section className="license-rules"><FileImage /><div><h2>Admission rules</h2><p>Public-domain, appropriately licensed, explicitly permitted, or DTF-owned media only. Each asset needs a source URL, creator, license, condition, view, stage, severity, and confirmation status.</p></div></section>
    </div>
  )
}
