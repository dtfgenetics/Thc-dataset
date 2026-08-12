import { ArrowLeft, ArrowRight, CheckCircle2, CircleAlert, ImageOff, Search } from 'lucide-react'
import { useDeferredValue, useMemo, useState } from 'react'
import { categoryOrder, issues } from '../data/issues'
import type { IssueCategory, IssueRecord } from '../types'
import { ImagePlaceholder } from './icons'

interface IssueLibraryProps {
  initialSlug?: string
  onClearInitialSlug: () => void
}

export function IssueLibrary({ initialSlug, onClearInitialSlug }: IssueLibraryProps) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<IssueCategory | 'All'>('All')
  const [selected, setSelected] = useState<IssueRecord | null>(() => issues.find((item) => item.slug === initialSlug) ?? null)
  const deferredQuery = useDeferredValue(query)

  const filtered = useMemo(() => {
    const needle = deferredQuery.trim().toLowerCase()
    return issues.filter((item) => {
      const categoryMatch = category === 'All' || item.category === category
      const queryMatch = !needle || [item.name, item.scientificName, item.summary, item.category, ...item.indicators].filter(Boolean).join(' ').toLowerCase().includes(needle)
      return categoryMatch && queryMatch
    })
  }, [category, deferredQuery])

  const openIssue = (record: IssueRecord) => {
    setSelected(record)
    onClearInitialSlug()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (selected) return <IssueDetail issue={selected} onBack={() => setSelected(null)} />

  const usedCategories = categoryOrder.filter((item) => issues.some((issue) => issue.category === item))
  return (
    <div className="view-container library-view">
      <div className="view-intro">
        <div><span>Verified knowledge base</span><h1>Issue library</h1><p>Separate conditions, explicit look-alikes, confirmation limits, and corrective guidance. No combined labels.</p></div>
        <div className="library-count"><strong>{filtered.length}</strong><small>visible records</small></div>
      </div>
      <div className="library-tools">
        <label className="search-field"><Search size={19} /><input aria-label="Search issue library" placeholder="Search deficiency, mite, mildew…" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
        <div className="filter-row" aria-label="Filter by category"><button className={category === 'All' ? 'active' : ''} onClick={() => setCategory('All')}>All</button>{usedCategories.map((item) => <button key={item} className={category === item ? 'active' : ''} onClick={() => setCategory(item)}>{item}</button>)}</div>
      </div>
      <div className="issue-list">
        {filtered.map((item) => (
          <article key={item.id} className="issue-row">
            <div className="issue-thumb">{item.media[0]?.thumbnailUrl ? <img src={item.media[0].thumbnailUrl} alt={item.media[0].alt} /> : <ImagePlaceholder label={`No licensed reference image available for ${item.name}`} />}</div>
            <div className="issue-row-body"><div className="issue-meta"><span>{item.category}</span><span className={`severity severity-${item.severity}`}>{item.severity}</span></div><h2>{item.name}</h2>{item.scientificName ? <em>{item.scientificName}</em> : null}<p>{item.summary}</p><ul>{item.indicators.slice(0, 3).map((indicator) => <li key={indicator}>{indicator}</li>)}</ul></div>
            <div className="issue-row-status"><span className={`review review-${item.reviewStatus}`}>{item.reviewStatus}</span><span>{item.media.length ? `${item.media.length} reviewed images` : <><ImageOff size={15} /> Image gap</>}</span><span>{item.sources.length} source{item.sources.length === 1 ? '' : 's'}</span><button onClick={() => openIssue(item)} aria-label={`Open ${item.name}`}>Open guide <ArrowRight size={17} /></button></div>
          </article>
        ))}
      </div>
      {!filtered.length ? <div className="empty-state"><Search /><h2>No matching records</h2><p>Try another term or remove the category filter.</p></div> : null}
    </div>
  )
}

function IssueDetail({ issue, onBack }: { issue: IssueRecord; onBack: () => void }) {
  return (
    <div className="view-container issue-detail">
      <button className="back-button" onClick={onBack}><ArrowLeft size={18} /> Back to issue library</button>
      <header className="detail-header"><div><div className="issue-meta"><span>{issue.category}</span><span className={`severity severity-${issue.severity}`}>{issue.severity}</span></div><h1>{issue.name}</h1>{issue.scientificName ? <em>{issue.scientificName}</em> : null}<p>{issue.summary}</p></div><div className="detail-status"><span className={`review review-${issue.reviewStatus}`}>{issue.reviewStatus}</span><small>Scientific review status</small></div></header>
      <section className="detail-gallery" aria-labelledby="gallery-heading"><div className="detail-section-title"><h2 id="gallery-heading">Reference images</h2><span>{issue.media.length} licensed and reviewed</span></div>{issue.media.length ? <div className="media-grid">{issue.media.map((media) => <figure key={media.id}><img src={media.url ?? media.thumbnailUrl} alt={media.alt} /><figcaption>{media.caption}<small>{media.creator} · {media.license}</small></figcaption></figure>)}</div> : <div className="media-gap"><ImagePlaceholder label={`Reference media pending for ${issue.name}`} /><div><ImageOff /><h3>Verified images are still missing</h3><p>This record will not pretend a text description is a reference photograph. Media must include a source, allowed-use license, and confirmation status.</p></div></div>}</section>
      <div className="detail-columns">
        <div><DetailList title="Signs that support it" items={issue.indicators} positive /><DetailList title="Evidence against it" items={issue.exclusions} /></div>
        <div><section className="detail-block"><h2>Symptom progression</h2><ol className="progression">{issue.progression.map((item) => <li key={item.stage}><strong>{item.stage}</strong><p>{item.description}</p></li>)}</ol></section><DetailList title="Look-alikes" items={issue.lookAlikes} /></div>
      </div>
      <section className="confirmation-box"><FlaskTitle /><div><h2>How to confirm</h2><ul>{issue.confirmation.map((item) => <li key={item}>{item}</li>)}</ul>{issue.category === 'Viroid' || issue.category === 'Virus' || issue.category === 'Phytoplasma / Spiroplasma' ? <p className="lab-warning"><CircleAlert size={17} /> Visual evidence cannot confirm this category. Use validated laboratory testing.</p> : null}</div></section>
      <div className="action-grid"><DetailList title="Do now" items={issue.immediateActions} positive /><DetailList title="Corrective plan" items={issue.correctivePlan} /><DetailList title="Prevention" items={issue.prevention} /><DetailList title="Do not do" items={issue.warnings} /></div>
      <section className="sources-block"><h2>Sources</h2>{issue.sources.length ? <ol>{issue.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a><span>{source.organization}{source.year ? ` · ${source.year}` : ''}</span></li>)}</ol> : <p>This provisional record still needs mapped academic or extension sources before it can be marked reviewed.</p>}</section>
    </div>
  )
}

function DetailList({ title, items, positive = false }: { title: string; items: string[]; positive?: boolean }) {
  return <section className="detail-block"><h2>{title}</h2><ul className={positive ? 'positive-list' : ''}>{items.map((item) => <li key={item}>{positive ? <CheckCircle2 size={16} /> : null}{item}</li>)}</ul></section>
}

function FlaskTitle() { return <div className="flask-title" aria-hidden="true">LAB</div> }
