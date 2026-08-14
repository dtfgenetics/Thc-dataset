import type { Differential, EvidenceFile, GrowContext, IssueRecord } from '../types'

const normalise = (value: string) => value.trim().toLowerCase()

const laboratoryBoundedCategories = new Set([
  'Bacterial pathogen',
  'Viroid',
  'Virus',
  'Phytoplasma / Spiroplasma',
])

const microscopicMiteSlugs = new Set(['hemp-russet-mite', 'broad-mite'])

const needsRootZoneChemistry = (issue: IssueRecord) =>
  issue.category === 'Nutrient deficiency'
  || issue.category === 'Nutrient toxicity'
  || issue.category === 'Water / root-zone'
  || issue.category === 'Root pathogen'

const needsWateringContext = (issue: IssueRecord) =>
  issue.category === 'Water / root-zone'
  || issue.category === 'Root pathogen'
  || issue.category === 'Environmental stress'

export function rankDifferentials(
  records: IssueRecord[],
  context: GrowContext,
  evidence: EvidenceFile[],
): Differential[] {
  const selected = new Set(context.symptoms.map(normalise))
  const hasRootView = evidence.some((item) => item.slot === 'root-crown')
  const hasUnderside = evidence.some((item) => item.slot === 'underside')
  const hasWholePlant = evidence.some((item) => item.slot === 'whole-plant')
  const hasCloseUp = evidence.some((item) => item.slot === 'close-up')

  return records
    .map((issue) => {
      const matched = issue.indicators.filter((indicator) => selected.has(normalise(indicator)))
      const contradictory = issue.exclusions.filter((indicator) => selected.has(normalise(indicator)))
      let score = matched.length * 3 - contradictory.length * 4

      if (context.stage && issue.stages.includes(context.stage)) score += 1
      if (hasRootView && (issue.category === 'Root pathogen' || issue.category === 'Water / root-zone')) score += 1
      if (hasUnderside && (issue.category === 'Mite' || issue.category === 'Insect')) score += 1

      const missing: string[] = []
      if (!hasWholePlant) missing.push('whole-plant view')
      if (!hasCloseUp) missing.push('affected-tissue close-up')
      if ((issue.category === 'Mite' || issue.category === 'Insect') && !hasUnderside) missing.push('leaf-underside image')
      if ((issue.category === 'Root pathogen' || issue.category === 'Water / root-zone') && !hasRootView) missing.push('root or crown view')
      if (laboratoryBoundedCategories.has(issue.category)) missing.push('validated laboratory test')
      if (microscopicMiteSlugs.has(issue.slug)) missing.push('microscope-confirmed mite identification')

      // Optional grow context is requested only when it can separate plausible causes.
      // It must never block the first image/video analysis.
      if (needsRootZoneChemistry(issue) && !context.ph) missing.push('measured pH')
      if (needsRootZoneChemistry(issue) && !context.ec) missing.push('measured EC/PPM')
      if (needsWateringContext(issue) && !context.watering) missing.push('recent irrigation / substrate-moisture context')

      let confidence: Differential['confidence'] = score >= 9 && contradictory.length === 0 ? 'High' : score >= 4 ? 'Moderate' : 'Low'

      // Evidence gates prevent symptom overlap from being mistaken for confirmation.
      if (laboratoryBoundedCategories.has(issue.category)) confidence = 'Low'

      if (issue.category === 'Root pathogen' && !hasRootView) confidence = 'Low'

      if (issue.category === 'Mite') {
        if (!hasUnderside) confidence = 'Low'
        else if (microscopicMiteSlugs.has(issue.slug) && confidence === 'High') confidence = 'Moderate'
      }

      if (issue.category === 'Insect' && !hasUnderside && confidence === 'High') confidence = 'Moderate'

      if (
        (issue.category === 'Nutrient deficiency' || issue.category === 'Nutrient toxicity')
        && (!context.ph || !context.ec)
        && confidence === 'High'
      ) {
        confidence = 'Moderate'
      }

      if ((!hasWholePlant || !hasCloseUp) && confidence === 'High') confidence = 'Moderate'

      return {
        issue,
        confidence,
        score,
        supporting: matched,
        contradicting: contradictory,
        missing,
      } satisfies Differential
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
}

export async function inspectEvidenceFile(file: File) {
  const notes: string[] = []
  if (file.size < 90_000) notes.push('File is small; fine symptom detail may be missing.')
  if (file.size > 18_000_000) notes.push('Large file; upload may be slow on mobile data.')

  const url = URL.createObjectURL(file)
  try {
    if (file.type.startsWith('video/')) {
      const metadata = await new Promise<{ width: number; height: number; duration: number }>((resolve, reject) => {
        const video = document.createElement('video')
        video.onloadedmetadata = () => resolve({ width: video.videoWidth, height: video.videoHeight, duration: video.duration })
        video.onerror = reject
        video.src = url
      })
      if (metadata.duration > 30.5) notes.push('Video is longer than 30 seconds; trim it before analysis.')
      if (metadata.width < 720 || metadata.height < 480) notes.push('Low video resolution; fine symptom detail may be missing.')
      return { ...metadata, quality: notes.length ? 'review' as const : 'good' as const, notes }
    }
    const dimensions = await new Promise<{ width: number; height: number }>((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight })
      image.onerror = reject
      image.src = url
    })
    if (dimensions.width < 900 || dimensions.height < 700) notes.push('Low resolution; retake closer or at a higher setting.')
    if (Math.max(dimensions.width, dimensions.height) / Math.min(dimensions.width, dimensions.height) > 3) notes.push('Very narrow crop; include more surrounding tissue.')
    return { ...dimensions, quality: notes.length ? 'review' as const : 'good' as const, notes }
  } finally {
    URL.revokeObjectURL(url)
  }
}

export function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}
