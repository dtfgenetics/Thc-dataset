import { describe, expect, it } from 'vitest'
import type { EvidenceFile } from '../types'
import { analysisFilesForEvidence } from './visual-observations'

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

describe('analysisFilesForEvidence', () => {
  it('uses the untouched original when no derived view exists', () => {
    const item = evidence()
    expect(analysisFilesForEvidence(item)).toEqual([item.file])
    expect(item.file.name).toBe('original.jpg')
  })

  it('sends the original first and the derived detail second', () => {
    const original = new File(['original'], 'original.jpg', { type: 'image/jpeg' })
    const derived = new File(['detail'], 'original-detail.jpg', { type: 'image/jpeg' })
    const item = evidence({ file: original, analysisFile: derived })
    expect(analysisFilesForEvidence(item)).toEqual([original, derived])
    expect(item.file).toBe(original)
    expect(item.file.name).toBe('original.jpg')
  })
})
