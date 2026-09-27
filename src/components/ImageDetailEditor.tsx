import { useEffect, useMemo, useState } from 'react'

interface ImageDetailEditorProps {
  source: File
  open: boolean
  onClose: () => void
  onApply: (file: File, transform: { zoom: number; rotation: number; panX: number; panY: number }) => void
}

function loadImage(file: File) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => { URL.revokeObjectURL(url); resolve(image) }
    image.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Unable to read this image.')) }
    image.src = url
  })
}

function canvasBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('Unable to create the detail image.')), 'image/jpeg', 0.92)
  })
}

export function ImageDetailEditor({ source, open, onClose, onApply }: ImageDetailEditorProps) {
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [panX, setPanX] = useState(0)
  const [panY, setPanY] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const previewUrl = useMemo(() => open ? URL.createObjectURL(source) : '', [open, source])

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])

  useEffect(() => {
    if (!open) return
    setZoom(1)
    setRotation(0)
    setPanX(0)
    setPanY(0)
    setError('')
  }, [open, source])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  const apply = async () => {
    setSaving(true)
    setError('')
    try {
      const image = await loadImage(source)
      const width = 1200
      const height = 900
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const context = canvas.getContext('2d')
      if (!context) throw new Error('Canvas is not available in this browser.')

      context.fillStyle = '#111'
      context.fillRect(0, 0, width, height)
      const radians = rotation * Math.PI / 180
      const rotatedWidth = Math.abs(image.naturalWidth * Math.cos(radians)) + Math.abs(image.naturalHeight * Math.sin(radians))
      const rotatedHeight = Math.abs(image.naturalWidth * Math.sin(radians)) + Math.abs(image.naturalHeight * Math.cos(radians))
      const coverScale = Math.max(width / Math.max(1, rotatedWidth), height / Math.max(1, rotatedHeight))
      const scale = coverScale * zoom

      context.save()
      context.translate(width / 2 + (panX / 100) * width * 0.3, height / 2 + (panY / 100) * height * 0.3)
      context.rotate(radians)
      context.scale(scale, scale)
      context.drawImage(image, -image.naturalWidth / 2, -image.naturalHeight / 2)
      context.restore()

      const blob = await canvasBlob(canvas)
      const baseName = source.name.replace(/\.[^.]+$/, '') || 'diagnostic-photo'
      const file = new File([blob], `${baseName}-detail.jpg`, { type: 'image/jpeg', lastModified: Date.now() })
      onApply(file, { zoom, rotation, panX, panY })
      onClose()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to create the detail image.')
    } finally {
      setSaving(false)
    }
  }

  const reset = () => { setZoom(1); setRotation(0); setPanX(0); setPanY(0) }

  return (
    <div className="image-detail-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="image-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="image-detail-title">
        <div className="image-detail-heading">
          <div>
            <span>Derived analysis view</span>
            <h3 id="image-detail-title">Focus the symptom without replacing the original</h3>
            <p>The original upload is always retained. This crop is an additional view used for visual analysis.</p>
          </div>
          <button type="button" className="image-detail-close" onClick={onClose} aria-label="Close image detail editor">×</button>
        </div>

        <div className="image-detail-stage" aria-label="Crop preview">
          <img
            src={previewUrl}
            alt="Diagnostic crop preview"
            style={{
              transform: `translate(${panX * 0.3}%, ${panY * 0.3}%) rotate(${rotation}deg) scale(${zoom})`,
            }}
          />
          <div className="image-detail-frame" aria-hidden="true" />
        </div>

        <div className="image-detail-controls">
          <label><span>Zoom</span><input type="range" min="1" max="3" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
          <label><span>Move left / right</span><input type="range" min="-100" max="100" step="1" value={panX} onChange={(event) => setPanX(Number(event.target.value))} /></label>
          <label><span>Move up / down</span><input type="range" min="-100" max="100" step="1" value={panY} onChange={(event) => setPanY(Number(event.target.value))} /></label>
          <label><span>Rotate</span><input type="range" min="-180" max="180" step="1" value={rotation} onChange={(event) => setRotation(Number(event.target.value))} /></label>
        </div>

        <div className="image-detail-actions">
          <button type="button" onClick={() => setRotation((value) => value - 90)}>Rotate −90°</button>
          <button type="button" onClick={() => setRotation((value) => value + 90)}>Rotate +90°</button>
          <button type="button" onClick={reset}>Reset</button>
          <button type="button" className="primary" onClick={apply} disabled={saving}>{saving ? 'Creating detail…' : 'Use detail for analysis'}</button>
        </div>
        {error ? <p className="image-detail-error" role="alert">{error}</p> : null}
        <p className="image-detail-evidence-rule"><strong>Evidence rule:</strong> the derived detail can improve visibility, but it never replaces the original image as source context or ground truth.</p>
      </section>
    </div>
  )
}
