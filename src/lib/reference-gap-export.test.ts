import { describe, expect, it } from 'vitest'
import { buildReferenceGapCsv } from './reference-gap-export'

describe('missing-reference editorial CSV', () => {
  it('exports a labeled, UTF-8 spreadsheet-friendly report without claiming image rights', () => {
    const csv = buildReferenceGapCsv([{
      slug: 'example-guide',
      name: 'Example, deficiency',
      category: 'Nutrient deficiency',
      scientificName: undefined,
      affectedParts: ['lower leaves', 'petioles'],
      confirmation: ['Check pH', 'Compare a second plant'],
      lookAlikes: ['Water stress'],
    }])
    expect(csv.startsWith('\uFEFF')).toBe(true)
    expect(csv).toContain('"Guide ID","Condition guide","Category"')
    expect(csv).toContain('"example-guide","Example, deficiency","Nutrient deficiency"')
    expect(csv).toContain('"lower leaves; petioles"')
    expect(csv).toContain('"Check pH; Compare a second plant"')
    expect(csv).toContain('No approved displayable reference linked; source and rights review required')
    expect(csv.endsWith('\r\n')).toBe(true)
  })

  it('escapes quotes and prevents spreadsheet formula execution in user-visible catalog fields', () => {
    const csv = buildReferenceGapCsv([{
      slug: 'test',
      name: '=HYPERLINK("unsafe")',
      category: 'Insufficient evidence',
      scientificName: '+SUM(1,2)',
      affectedParts: ['"leaf", edge'],
      confirmation: ['@malicious'],
      lookAlikes: ['-10'],
    }])
    expect(csv).toContain('"\'=HYPERLINK(""unsafe"")"')
    expect(csv).toContain('"\'+SUM(1,2)"')
    expect(csv).toContain('"""leaf"", edge"')
    expect(csv).toContain('"\'@malicious"')
    expect(csv).toContain('"\'-10"')
  })

  it.each([
    ['zero-width space', 0x200b],
    ['Arabic letter mark', 0x061c],
    ['soft hyphen', 0x00ad],
    ['C1 next-line control', 0x0085],
    ['word joiner', 0x2060],
  ])('quotes formula operators preceded by %s', (_description, codePoint) => {
    const label = String.fromCodePoint(codePoint) + '=1+1'
    const csv = buildReferenceGapCsv([{
      slug: 'format-controls',
      name: label,
      category: 'Insufficient evidence',
      scientificName: undefined,
      affectedParts: [],
      confirmation: [],
      lookAlikes: [],
    }])
    expect(csv).toContain(JSON.stringify("'" + label))
  })

  it('does not alter ordinary text containing formula characters later in a cell', () => {
    const csv = buildReferenceGapCsv([{
      slug: 'ordinary',
      name: 'Label = not a formula',
      category: 'Insufficient evidence',
      scientificName: undefined,
      affectedParts: [],
      confirmation: [],
      lookAlikes: [],
    }])
    expect(csv).toContain('"Label = not a formula"')
  })

  it('returns headers for an empty filtered backlog', () => {
    const csv = buildReferenceGapCsv([])
    expect(csv).toContain('"Guide ID"')
    expect(csv).not.toContain('"example-guide"')
  })
})
