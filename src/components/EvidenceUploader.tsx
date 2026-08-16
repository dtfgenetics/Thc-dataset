import { AlertCircle, Aperture, Check, FileVideo, ImagePlus, Layers3, Lightbulb, LoaderCircle, Palette, Trash2 } from 'lucide-react'
import { useRef } from 'react'
import type { EvidenceFile, EvidenceSlot } from '../types'

const slots: Array<{ id: EvidenceSlot; title: string; guidance: string; accept: string }> = [
  { id: 'whole-plant', title: 'Whole plant', guidance: 'Include the pot and full canopy', accept: 'image/jpeg,image/png,image/webp' },
  { id: 'close-up', title: 'Affected close-up', guidance: 'Fill the frame with the symptom', accept: 'image/jpeg,image/png,image/webp' },
  { id: 'underside', title: 'Leaf underside', guidance: 'Show pests, eggs, or damage', accept: 'image/jpeg,image/png,image/webp' },
  { id: 'root-crown', title: 'Roots or crown', guidance: 'Use clean, natural light', accept: 'image/jpeg,image/png,image/webp' },
  { id: 'video', title: 'Optional video', guidance: 'Up to 30 seconds of movement or context', accept: 'video/mp4,video/webm,video/quicktime' },
]

interface EvidenceUploaderProps {
  evidence: EvidenceFile[]
  onFiles: (slot: EvidenceSlot, files: FileList) => void
  onRemove: (id: string) => void
}

export function EvidenceUploader({ evidence, onFiles, onRemove }: EvidenceUploaderProps) {
  const inputRefs = useRef<Partial<Record<EvidenceSlot, HTMLInputElement | null>>>({})

  return (
    <section className="evidence-section" aria-labelledby="evidence-title">
      <div className="section-heading">
        <div><span>Step 1</span><h2 id="evidence-title">Add plant evidence</h2></div>
        <p>Use recent, unfiltered media. Different views improve the comparison.</p>
      </div>

      <div className="evidence-grid">
        {slots.map((slot) => {
          const items = evidence.filter((item) => item.slot === slot.id)
          const item = items[0]
          return (
            <div className="evidence-slot" key={slot.id}>
              <label>{slot.title}</label>
              <button className={`upload-tile ${item ? 'has-file' : ''}`} onClick={() => inputRefs.current[slot.id]?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); if (event.dataTransfer.files.length) onFiles(slot.id, event.dataTransfer.files) }} type="button">
                {item ? (
                  <>
                    {item.file.type.startsWith('video/') ? <video src={item.previewUrl} muted /> : <img src={item.previewUrl} alt={`${slot.title} preview`} />}
                    {items.length > 1 ? <span className="file-count">+{items.length - 1} more</span> : null}
                    <span className={`quality-state ${item.quality}`}>
                      {item.quality === 'checking' ? <LoaderCircle className="spin" size={16} /> : item.quality === 'good' ? <Check size={16} /> : <AlertCircle size={16} />}
                      {item.quality === 'checking' ? 'Checking' : item.quality === 'good' ? 'Quality looks usable' : 'Review quality'}
                    </span>
                  </>
                ) : (
                  <><span className="upload-icon">{slot.id === 'video' ? <FileVideo /> : <ImagePlus />}</span><strong>{slot.id === 'video' ? 'Add video' : 'Add image'}</strong><small>or drag and drop</small></>
                )}
              </button>
              <input ref={(node) => { inputRefs.current[slot.id] = node }} type="file" accept={slot.accept} multiple={slot.id === 'close-up'} onChange={(event) => event.target.files?.length && onFiles(slot.id, event.target.files)} hidden />
              <p>{slot.guidance}</p>
              {item?.notes.length ? <ul className="quality-notes">{item.notes.map((note) => <li key={note}>{note}</li>)}</ul> : null}
              {item ? <button className="remove-file" onClick={() => onRemove(item.id)}><Trash2 size={14} /> Remove</button> : null}
            </div>
          )
        })}
      </div>
      <div className="privacy-note"><Check size={16} /><span>Uploads stay in your browser unless you explicitly choose visual analysis. DTF does not add uploaded media to its training dataset.</span></div>
      <div className="quality-criteria" aria-label="Photo quality checklist">
        <strong>Photo quality</strong>
        <span><Aperture /> Sharp focus</span>
        <span><Lightbulb /> Even light</span>
        <span><Palette /> Natural color</span>
        <span><Layers3 /> Multiple angles</span>
      </div>
    </section>
  )
}
