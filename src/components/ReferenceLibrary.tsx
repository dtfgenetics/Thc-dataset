import { ExternalLink, FileImage, ImageOff, Search } from 'lucide-react'
import { useDeferredValue, useMemo, useState } from 'react'
import { issues } from '../data/catalog'
import { isDisplayableMedia } from '../lib/media'
import { referenceMediaSources } from '../lib/reference-media-assets'
import { ImagePlaceholder } from './icons'
import { ResilientImage } from './ResilientImage'

export function ReferenceLibrary({ onOpenIssue, focusSlugs = [] }: { onOpenIssue: (slug: string) => void; focusSlugs?: string[] }) {
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query)
  const approvedMedia = issues.flatMap((issue) => issue.media.map((media) => ({ issue, media }))).filter(({ media }) => isDisplayableMedia(media) && (media.url || media.thumbnailUrl))
  const focusSet = useMemo(() => new Set(focusSlugs), [focusSlugs])
  const filtered = useMemo(() => approvedMedia.filter(({ issue, media }) => {
    const matchesQuery = `${issue.name} ${issue.category} ${media.caption}`.toLowerCase().includes(deferredQuery.toLowerCase())
    if (!matchesQuery) return false
    if (!deferredQuery.trim() && focusSet.size > 0) return focusSet.has(issue.slug)
    return true
  }), [approvedMedia, deferredQuery, focusSet])
  const showingFocused = !deferredQuery.trim() && focusSet.size > 0

  return (
    <div className="view-container references-view">
      <div className="view-intro">
        <div>
          <span>{showingFocused ? 'Active investigation evidence' : 'Licensed media only'}</span>
          <h1>Reference images</h1>
          <p>{showingFocused ? 'Showing reviewed visual evidence for the leading hypothesis and realistic alternatives in the active Grow Doc investigation.' : 'Every visible asset must carry its condition, source, allowed-use license, view, and confirmation method.'}</p>
        </div>
        <div className="library-count"><strong>{filtered.length}</strong><small>{showingFocused ? 'focused images' : 'approved images'}</small></div>
      </div>
      <label className="search-field reference-search"><Search size={19} /><input aria-label="Search reference images" placeholder="Search by issue or category" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
      {showingFocused ? <div className="reference-focus-note"><strong>Investigation filter active</strong><span>Leading differential plus up to four alternatives. Search to explore the full reviewed library.</span></div> : null}
      {filtered.length ? <div className="reference-grid">{filtered.map(({ issue, media }) => <figure key={media.id}><ResilientImage sources={referenceMediaSources(media, issue.slug)} alt={media.alt} fallback={<ImagePlaceholder label={`Licensed reference image unavailable for ${issue.name}`} />} /><figcaption><span>{focusSlugs[0] === issue.slug ? 'Leading hypothesis' : issue.category}</span><h2>{issue.name}</h2><p>{media.caption}</p><dl><div><dt>Confirmation</dt><dd>{media.confirmation}</dd></div><div><dt>License</dt><dd>{media.license ?? 'Missing'}</dd></div><div><dt>View</dt><dd>{media.view}</dd></div></dl><div><button onClick={() => onOpenIssue(issue.slug)}>Open guide</button>{media.sourceUrl ? <a href={media.sourceUrl} target="_blank" rel="noreferrer">Source <ExternalLink size={14} /></a> : null}</div></figcaption></figure>)}</div> : <div className="media-empty"><ImagePlaceholder label="Reference image library awaiting reviewed media" /><div><ImageOff /><h2>{showingFocused ? 'No reviewed reference image for this differential yet' : 'No approved photographs yet'}</h2><p>{showingFocused ? 'The diagnosis remains usable, but Grow Doc will not invent or substitute unreviewed imagery. Search the full library or continue with the recommended measurements and confirmation checks.' : 'The previous site counted text descriptions as reference records. This rebuild counts only actual media with usable licensing and scientific review metadata.'}</p>{!showingFocused ? <strong>Next content milestone: 1,096 reviewed images</strong> : null}</div></div>}
      <section className="license-rules"><FileImage /><div><h2>Admission rules</h2><p>Public-domain, appropriately licensed, explicitly permitted, or DTF-owned media only. Each asset needs a source URL, creator, license, condition, view, stage, severity, and confirmation status.</p></div></section>
    </div>
  )
}
