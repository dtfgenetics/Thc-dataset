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

  it.each([
    'https://creativecommons.org/licenses/by-nc-nd/4.0/',
    'https://creativecommons.org/licenses/by-nc-sa/4.0/',
    'CC BY–NC–ND 4.0',
    'CC BY—NC—SA 4.0',
  ])('blocks noncommercial license URLs and Unicode dashes: %s', (license) => {
    expect(isDisplayableMedia(example(license))).toBe(false)
  })

  it('blocks noncommercial use limitations even with a permissive license label', () => {
    expect(isDisplayableMedia(example('other', {
      useLimitations: ['Non-commercial reference display only'],
    }))).toBe(false)
  })

  it.each([
    'No commercial use',
    'Commercial reuse prohibited',
    'Commercial display not permitted',
  ])('blocks explicit use limitation: %s', (restriction) => {
    expect(isDisplayableMedia(example('CC BY 4.0', {
      useLimitations: [restriction],
    }))).toBe(false)
  })

  it.each([
    'Not for commercial use',
    'Commercial use requires written permission',
    'Commercial use not allowed',
    'Personal use only',
    'Educational use only',
  ])('blocks additional commercial-use limitations: %s', (restriction) => {
    expect(isDisplayableMedia(example('CC BY 4.0', {
      useLimitations: [restriction],
    }))).toBe(false)
  })

  it('rejects restrictions embedded in attribution metadata', () => {
    expect(isDisplayableMedia(example('CC BY 4.0', {
      requiredAttribution: 'Creator. Not for commercial use.',
    }))).toBe(false)
  })

  it('excludes restricted shared composite references', () => {
    const restricted = example('CC BY-NC 4.0', {
      sha256: 'c9200d6cb4fc0ee7a31908b9df06240a86ec6f2cf53fb8bece5098e4ee422952',
    })
    const owner = { slug: 'reference-owner', media: [restricted] } as IssueRecord
    const consumer = { slug: 'nitrogen-deficiency', media: [] } as unknown as IssueRecord
    expect(resolvedDisplayMediaForIssue(consumer, [owner, consumer])).toEqual([])
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
