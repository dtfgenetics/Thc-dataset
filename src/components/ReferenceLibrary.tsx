import { ExternalLink, FileImage, ImageOff, Search } from 'lucide-react'
import { useDeferredValue, useMemo, useState } from 'react'
import { issues } from '../data/catalog'
import { isDisplayableMedia } from '../lib/media'
import { ImagePlaceholder } from './icons'
import { ResilientImage } from './ResilientImage'

export function ReferenceLibrary({ onOpenIssue }: { onOpenIssue: (slug: string) => void }) {
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query)
  const approvedMedia = issues.flatMap((issue) => issue.media.map((media) => ({ issue, media }))).filter(({ media }) => isDisplayableMedia(media) && (media.url || media.thumbnailUrl))
  const filtered = useMemo(() => approvedMedia.filter(({ issue, media }) => `${issue.name} ${issue.category} ${media.caption}`.toLowerCase().includes(deferredQuery.toLowerCase())), [approvedMedia, deferredQuery])

  return (
    <div className="view-container references-view">
      <div className="view-intro"><div><span>Licensed media only</span><h1>Reference images</h1><p>Every visible asset must carry its condition, source, allowed-use license, view, and confirmation method.</p></div><div className="library-count"><strong>{approvedMedia.length}</strong><small>approved images</small></div></div>
      <label className="search-field reference-search"><Search size={19} /><input aria-label="Search reference images" placeholder="Search by issue or category" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
      {filtered.length ? <div className="reference-grid">{filtered.map(({ issue, media }) => <figure key={media.id}><ResilientImage sources={[media.thumbnailUrl, media.url]} alt={media.alt} fallback={<ImagePlaceholder label={`Licensed reference image unavailable for ${issue.name}`} />} /><figcaption><span>{issue.category}</span><h2>{issue.name}</h2><p>{media.caption}</p><dl><div><dt>Confirmation</dt><dd>{media.confirmation}</dd></div><div><dt>License</dt><dd>{media.license ?? 'Missing'}</dd></div><div><dt>View</dt><dd>{media.view}</dd></div></dl><div><button onClick={() => onOpenIssue(issue.slug)}>Open guide</button>{media.sourceUrl ? <a href={media.sourceUrl} target="_blank" rel="noreferrer">Source <ExternalLink size={14} /></a> : null}</div></figcaption></figure>)}</div> : <div className="media-empty"><ImagePlaceholder label="Reference image library awaiting reviewed media" /><div><ImageOff /><h2>No approved photographs yet</h2><p>The previous site counted text descriptions as reference records. This rebuild counts only actual media with usable licensing and scientific review metadata.</p><strong>Next content milestone: 1,096 reviewed images</strong></div></div>}
      <section className="license-rules"><FileImage /><div><h2>Admission rules</h2><p>Public-domain, appropriately licensed, explicitly permitted, or DTF-owned media only. Each asset needs a source URL, creator, license, condition, view, stage, severity, and confirmation status.</p></div></section>
    </div>
  )
}
