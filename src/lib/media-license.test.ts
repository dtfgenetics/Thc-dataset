import { describe, expect, it } from 'vitest'
import type { IssueRecord, MediaRecord } from '../types'
import { isDisplayableMedia, resolvedDisplayMediaForIssue } from './media'

const example = (license: string, overrides: Partial<MediaRecord> = {}): MediaRecord => ({
  id: 'institutional-reference',
  license,
  alt: 'Reference image',
  caption: 'Institutional reference image',
  mediaType: 'image',
  requiredAttribution: 'Creator and source',
  diagnosticLabel: 'reference only',
  hostSpecies: 'Cannabis sativa',
  hostContext: 'cannabis',
  useLimitations: ['No automated training'],
  displayPermission: 'permitted',
  reviewStatus: 'approved-reference',
  trainingPermission: 'not-permitted',
  view: 'close-up',
  confirmation: 'visual',
  trainingEligible: false,
  ...overrides,
})

describe('commercial media display licensing gate', () => {
  it.each([
    'CC BY-NC-ND 4.0',
    'CC BY-NC-SA 4.0',
    'CC BY-NC',
    'CC-BY-NC',
    'CC_BY_NC',
    'Creative Commons Attribution-NonCommercial-NoDerivatives',
  ])('blocks explicit noncommercial license %s', (license) => {
    expect(isDisplayableMedia(example(license))).toBe(false)
  })

  it('blocks noncommercial use limitations even with a permissive license label', () => {
    expect(isDisplayableMedia(example('other', {
      useLimitations: ['Non-commercial reference display only'],
    }))).toBe(false)
  })

  it('allows an approved CC BY reference', () => {
    expect(isDisplayableMedia(example('CC BY 4.0'))).toBe(true)
  })

  it('preserves permission and review gates', () => {
    expect(isDisplayableMedia(example('CC BY 4.0', { displayPermission: 'unknown' }))).toBe(false)
    expect(isDisplayableMedia(example('CC BY 4.0', { reviewStatus: 'candidate' }))).toBe(false)
  })

  it('does not resolve noncommercial images onto a diagnostic page', () => {
    const issue = { slug: 'curvularia', media: [example('CC BY-NC-ND 4.0')] } as IssueRecord
    expect(resolvedDisplayMediaForIssue(issue, [issue])).toEqual([])
  })
})
