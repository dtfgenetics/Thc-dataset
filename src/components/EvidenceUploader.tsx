import { AlertCircle, Camera, Check, FileVideo, ImagePlus, LoaderCircle, Plus, Trash2 } from 'lucide-react'
import { useRef } from 'react'
import type { EvidenceFile, EvidenceSlot } from '../types'

const primarySlots: Array<{ id: EvidenceSlot; title: string; guidance: string; accept: string }> = [
  { id: 'whole-plant', title: 'Whole plant', guidance: 'Include the pot and full canopy when possible.', accept: 'image/jpeg,image/png,image/webp' },
  { id: 'close-up', title: 'Affected area', guidance: 'Fill the frame with the clearest symptom. You can add up to four close-ups.', accept: 'image/jpeg,image/png,image/webp' },
]

const extraSlots: Array<{ id: EvidenceSlot; title: string; guidance: string; accept: string }> = [
  { id: 'underside', title: 'Leaf underside', guidance: 'Useful for mites, thrips, eggs, webbing, and feeding injury.', accept: 'image/jpeg,image/png,image/webp' },
  { id: 'root-crown', title: 'Roots or crown', guidance: 'Useful when wilting, root-zone stress, or root disease is possible.', accept: 'image/jpeg,image/png,image/webp' },
  { id: 'video', title: 'Short video', guidance: 'Up to 30 seconds for movement, canopy context, or a better sweep of the plant.', accept: 'video/mp4,video/webm,video/quicktime' },
]

interface EvidenceUploaderProps {
  evidence: EvidenceFile[]
  onFiles: (slot: EvidenceSlot, files: FileList) => void
  onRemove: (id: string) => void
}

export function EvidenceUploader({ evidence, onFiles, onRemove }: EvidenceUploaderProps) {
  const inputRefs = useRef<Partial<Record<EvidenceSlot, HTMLInputElement | null>>>({})

  const renderSlot = (slot: (typeof primarySlots)[number], compact = false) => {
    const items = evidence.filter((item) => item.slot === slot.id)
    const item = items[0]

    return (
      <div className={`evidence-slot ${compact ? 'compact' : ''}`} key={slot.id}>
        <div className="evidence-slot-heading">
          <div><strong>{slot.title}</strong><small>{slot.guidance}</small></div>
          {items.length ? <span>{items.length} added</span> : null}
        </div>

        <button
          className={`upload-tile ${item ? 'has-file' : ''}`}
          onClick={() => inputRefs.current[slot.id]?.click()}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => { event.preventDefault(); if (event.dataTransfer.files.length) onFiles(slot.id, event.dataTransfer.files) }}
          type="button"
        >
          {item ? (
            <>
              {item.file.type.startsWith('video/') ? <video src={item.previewUrl} muted /> : <img src={item.previewUrl} alt={`${slot.title} preview`} />}
              <span className={`quality-state ${item.quality}`}>
                {item.quality === 'checking' ? <LoaderCircle className="spin" size={16} /> : item.quality === 'good' ? <Check size={16} /> : <AlertCircle size={16} />}
                {item.quality === 'checking' ? 'Checking file' : item.quality === 'good' ? 'Resolution looks usable' : 'Review file quality'}
              </span>
              <span className="replace-media"><Plus size={15} /> Replace</span>
            </>
          ) : (
            <>
              <span className="upload-icon">{slot.id === 'video' ? <FileVideo /> : <Camera />}</span>
              <strong>{slot.id === 'video' ? 'Add video' : 'Take or add photo'}</strong>
              <small>Camera, gallery, or drag and drop</small>
            </>
          )}
        </button>

        <input
          ref={(node) => { inputRefs.current[slot.id] = node }}
          type="file"
          accept={slot.accept}
          multiple={slot.id === 'close-up'}
          capture={slot.id === 'video' ? undefined : 'environment'}
          onChange={(event) => event.target.files?.length && onFiles(slot.id, event.target.files)}
          hidden
        />

        {items.length ? (
          <div className="evidence-preview-rail" aria-label={`${slot.title} files`}>
            {items.map((entry, index) => (
              <div className="evidence-preview-item" key={entry.id}>
                {entry.file.type.startsWith('video/') ? <FileVideo size={17} /> : <img src={entry.previewUrl} alt={`${slot.title} ${index + 1}`} />}
                <span>{entry.file.name || `${slot.title} ${index + 1}`}</span>
                <button type="button" onClick={() => onRemove(entry.id)} aria-label={`Remove ${entry.file.name || slot.title}`}><Trash2 size={14} /></button>
              </div>
            ))}
          </div>
        ) : null}

        {item?.notes.length ? <ul className="quality-notes">{item.notes.map((note) => <li key={note}>{note}</li>)}</ul> : null}
      </div>
    )
  }

  return (
    <section className="evidence-section" aria-labelledby="evidence-title">
      <div className="section-heading">
        <div><span>Step 1</span><h2 id="evidence-title">Start with a clear photo</h2></div>
        <p>One useful image is enough to begin. Add extra views only when they help separate look-alikes.</p>
      </div>

      <div className="primary-evidence-grid">
        {primarySlots.map((slot) => renderSlot(slot))}
      </div>

      <details className="optional-evidence">
        <summary><ImagePlus size={18} /><span><strong>Add another useful view</strong><small>Underside, roots/crown, or a short video</small></span><Plus size={17} /></summary>
        <div className="optional-evidence-grid">
          {extraSlots.map((slot) => renderSlot(slot, true))}
        </div>
      </details>

      <div className="privacy-note"><Check size={16} /><span>Your upload is for this diagnostic session. It is not added to the training dataset without separate explicit consent.</span></div>
    </section>
  )
}
