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

  it('returns headers for an empty filtered backlog', () => {
    const csv = buildReferenceGapCsv([])
    expect(csv).toContain('"Guide ID"')
    expect(csv).not.toContain('"example-guide"')
  })
})
