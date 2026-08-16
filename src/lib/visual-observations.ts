import type { EvidenceFile } from '../types'

export interface VisualObservationFeature {
  observation: string
  confidence: 'low' | 'moderate' | 'high'
}

export interface VisualObservationResult {
  provider: string
  model: string
  summary: string
  matchedIndicators: string[]
  visibleFeatures: VisualObservationFeature[]
  uncertainFeatures: string[]
  qualityNotes: string[]
  suggestedNextViews: string[]
  unknownOrOutOfScope: boolean
  providerDataUseNotice?: string
}

const endpoint = import.meta.env.VITE_VISUAL_OBSERVATION_ENDPOINT || '/thc-grow-doc/api/visual-observations.php'

function waitForEvent(target: EventTarget, event: string) {
  return new Promise<void>((resolve, reject) => {
    const onSuccess = () => { cleanup(); resolve() }
    const onError = () => { cleanup(); reject(new Error(`Unable to read media (${event}).`)) }
    const cleanup = () => {
      target.removeEventListener(event, onSuccess)
      target.removeEventListener('error', onError)
    }
    target.addEventListener(event, onSuccess, { once: true })
    target.addEventListener('error', onError, { once: true })
  })
}

async function videoFrames(file: File): Promise<Array<{ blob: Blob; name: string }>> {
  const url = URL.createObjectURL(file)
  const video = document.createElement('video')
  video.preload = 'metadata'
  video.muted = true
  video.playsInline = true
  video.src = url

  try {
    await waitForEvent(video, 'loadedmetadata')
    const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 1
    const candidates = [Math.min(0.5, duration * 0.1), duration * 0.5, Math.max(0, duration - 0.5)]
    const times = [...new Set(candidates.map((value) => Math.max(0, Math.min(duration, Number(value.toFixed(2))))))]
    const frames: Array<{ blob: Blob; name: string }> = []

    for (const [index, time] of times.entries()) {
      if (Math.abs(video.currentTime - time) > 0.05) {
        video.currentTime = time
        await waitForEvent(video, 'seeked')
      }
      if (!video.videoWidth || !video.videoHeight) continue

      const maxDimension = 1600
      const scale = Math.min(1, maxDimension / Math.max(video.videoWidth, video.videoHeight))
      const canvas = document.createElement('canvas')
      canvas.width = Math.max(1, Math.round(video.videoWidth * scale))
      canvas.height = Math.max(1, Math.round(video.videoHeight * scale))
      const context = canvas.getContext('2d')
      if (!context) continue
      context.drawImage(video, 0, 0, canvas.width, canvas.height)
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.88))
      if (blob) frames.push({ blob, name: `video-frame-${index + 1}.jpg` })
    }

    return frames
  } finally {
    URL.revokeObjectURL(url)
    video.removeAttribute('src')
    video.load()
  }
}

async function buildObservationMedia(evidence: EvidenceFile[]) {
  const media: Array<{ blob: Blob; name: string }> = []
  for (const item of evidence) {
    if (item.file.type.startsWith('image/')) {
      media.push({ blob: item.file, name: item.file.name || `${item.slot}.jpg` })
      continue
    }
    if (item.file.type.startsWith('video/')) {
      try {
        media.push(...await videoFrames(item.file))
      } catch {
        // Video frame extraction is best-effort. Image evidence can still proceed.
      }
    }
  }
  return media.slice(0, 8)
}

const stringArray = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

export async function requestVisualObservations(
  evidence: EvidenceFile[],
  allowedIndicators: string[],
): Promise<VisualObservationResult> {
  if (!evidence.length) throw new Error('Add at least one image or video before visual analysis.')
  const media = await buildObservationMedia(evidence)
  if (!media.length) throw new Error('No supported image frames were available for visual analysis.')

  const form = new FormData()
  media.forEach((item) => form.append('files[]', item.blob, item.name))
  form.append('allowedIndicators', JSON.stringify(allowedIndicators))

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'X-THC-Visual-Request': '1' },
    body: form,
    credentials: 'same-origin',
  })

  const payload = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok) {
    const message = typeof payload.error === 'string' ? payload.error : `Visual analysis failed (${response.status}).`
    throw new Error(message)
  }

  const allowed = new Set(allowedIndicators)
  const rawFeatures = Array.isArray(payload.visibleFeatures) ? payload.visibleFeatures : []
  const visibleFeatures = rawFeatures.flatMap((feature) => {
    if (!feature || typeof feature !== 'object') return []
    const record = feature as Record<string, unknown>
    if (typeof record.observation !== 'string') return []
    const confidence = record.confidence === 'high' || record.confidence === 'moderate' || record.confidence === 'low'
      ? record.confidence
      : 'low'
    return [{ observation: record.observation, confidence } satisfies VisualObservationFeature]
  })

  return {
    provider: typeof payload.provider === 'string' ? payload.provider : 'configured visual service',
    model: typeof payload.model === 'string' ? payload.model : 'unknown',
    summary: typeof payload.summary === 'string' ? payload.summary : '',
    matchedIndicators: stringArray(payload.matchedIndicators).filter((item) => allowed.has(item)),
    visibleFeatures,
    uncertainFeatures: stringArray(payload.uncertainFeatures),
    qualityNotes: stringArray(payload.qualityNotes),
    suggestedNextViews: stringArray(payload.suggestedNextViews),
    unknownOrOutOfScope: payload.unknownOrOutOfScope === true,
    providerDataUseNotice: typeof payload.providerDataUseNotice === 'string' ? payload.providerDataUseNotice : undefined,
  }
}
