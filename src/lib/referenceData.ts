export interface ReferenceImageRecord {
  id: string
  datasetId?: string
  path: string
  filename: string
  folder: string
  labels: string[]
  searchText: string
  sha256: string
  sizeBytes: number
  extension: string
  width: number
  height: number
}

export async function loadReferenceImageIndex(): Promise<ReferenceImageRecord[]> {
  const response = await fetch('/reference-image-index.json')
  if (!response.ok) {
    throw new Error(`Failed to load reference index: ${response.status}`)
  }

  const payload = await response.json()
  if (!payload || !Array.isArray(payload.images)) {
    return []
  }

  return payload.images as ReferenceImageRecord[]
}

export function searchReferenceImageIndex(records: ReferenceImageRecord[], query: string) {
  const value = query.trim().toLowerCase()
  if (!value) return []

  return records.filter((record) => {
    const haystack = [
      record.datasetId,
      record.filename,
      record.folder,
      record.path,
      record.searchText,
      record.sha256,
      ...(record.labels ?? []),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()

    return haystack.includes(value)
  }).slice(0, 12)
}
