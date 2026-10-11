import type { IssueRecord } from '../types'

type ReferenceGap = Pick<IssueRecord, 'slug' | 'name' | 'category' | 'scientificName' | 'affectedParts' | 'confirmation' | 'lookAlikes'>

const headers = [
  'Guide ID', 'Condition guide', 'Category', 'Scientific name',
  'Affected plant parts', 'Verification checks', 'Look-alikes', 'Visual evidence status',
]

function csvCell(value: string): string {
  // Spreadsheet applications may evaluate imported cells beginning with formula
  // operators. Prefix such content with an apostrophe before quoting it.
  const safe = /^[\s\u0000-\u001f]*[=+\-@]/.test(value) ? `'${value}` : value
  return `"${safe.replace(/"/g, '""')}"`
}

/** Public editorial backlog only. No image rights, diagnoses or training eligibility are inferred. */
export function buildReferenceGapCsv(guides: readonly ReferenceGap[]): string {
  const rows = guides.map((guide) => [
    guide.slug,
    guide.name,
    guide.category,
    guide.scientificName ?? '',
    guide.affectedParts.join('; '),
    guide.confirmation.slice(0, 3).join('; '),
    guide.lookAlikes.slice(0, 3).join('; '),
    'No approved displayable reference linked; source and rights review required',
  ])
  return '\uFEFF' + [headers, ...rows].map((row) => row.map((cell) => csvCell(String(cell))).join(',')).join('\r\n') + '\r\n'
}
