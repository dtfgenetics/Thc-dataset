import { describe, expect, it } from 'vitest'
import type { EvidenceFile } from '../types'
import { preferredAnalysisFile } from './visual-observations'

function evidence(overrides: Partial<EvidenceFile> = {}): EvidenceFile {
  return {
    id: 'evidence-1',
    file: new File(['original'], 'original.jpg', { type: 'image/jpeg' }),
    previewUrl: 'blob:original',
    slot: 'close-up',
    quality: 'good',
    notes: [],
    ...overrides,
  }
}

describe('preferredAnalysisFile', () => {
  it('uses the untouched original when no derived view exists', () => {
    const item = evidence()
    expect(preferredAnalysisFile(item)).toBe(item.file)
    expect(item.file.name).toBe('original.jpg')
  })

  it('prefers a derived analysis view without replacing the original', () => {
    const original = new File(['original'], 'original.jpg', { type: 'image/jpeg' })
    const derived = new File(['detail'], 'original-detail.jpg', { type: 'image/jpeg' })
    const item = evidence({ file: original, analysisFile: derived })
    expect(preferredAnalysisFile(item)).toBe(derived)
    expect(item.file).toBe(original)
    expect(item.file.name).toBe('original.jpg')
  })
})
