import fs from 'node:fs/promises'

const manualSpec = JSON.parse(await fs.readFile('data/reference-crop-spec.json', 'utf8'))
const gridSpec = JSON.parse(await fs.readFile('data/reference-grid-crop-spec.json', 'utf8'))
const cropManifest = JSON.parse(await fs.readFile('images/reference/crops-manifest.json', 'utf8'))
const releaseManifest = JSON.parse(await fs.readFile('data/manifest.json', 'utf8'))

const errors = []
const manual = Array.isArray(manualSpec.crops) ? manualSpec.crops : []
const grids = Array.isArray(gridSpec.grids) ? gridSpec.grids : []
const generated = Array.isArray(cropManifest.records) ? cropManifest.records : []

const expected = new Map()
for (const crop of manual) {
  if (!crop.id) errors.push('manual crop missing id')
  else if (expected.has(crop.id)) errors.push(`duplicate expected crop id ${crop.id}`)
  else expected.set(crop.id, crop)
}

let gridDerivedCount = 0
for (const grid of grids) {
  const xs = grid.xBands
  const ys = grid.yBands
  const columns = grid.columns
  const rows = grid.rows
  if (!Array.isArray(xs) || !Array.isArray(ys) || !Array.isArray(columns) || !Array.isArray(rows)) {
    errors.push(`${grid.id || '<grid>'}: incomplete grid arrays`)
    continue
  }
  if (xs.length !== columns.length) errors.push(`${grid.id}: xBands/columns mismatch`)
  if (ys.length !== rows.length) errors.push(`${grid.id}: yBands/rows mismatch`)
  for (let ci = 0; ci < Math.min(xs.length, columns.length); ci++) {
    for (let ri = 0; ri < Math.min(ys.length, rows.length); ri++) {
      const column = columns[ci]
      const row = rows[ri]
      const id = `crop-${column.id}-${row.id}`
      const expectedRecord = {
        id,
        parentId: grid.parentId,
        parentPath: grid.parentPath,
        sourceGroupId: grid.sourceGroupId,
        issueSlug: column.issueSlug,
        box: [xs[ci][0], ys[ri][0], xs[ci][1], ys[ri][1]],
        label: `${column.id}-${row.id}`,
      }
      if (expected.has(id)) errors.push(`duplicate expected crop id ${id}`)
      else expected.set(id, expectedRecord)
      gridDerivedCount++
    }
  }
}

const generatedById = new Map()
for (const record of generated) {
  if (!record.id) {
    errors.push('generated crop missing id')
    continue
  }
  if (generatedById.has(record.id)) errors.push(`duplicate generated crop id ${record.id}`)
  else generatedById.set(record.id, record)
}

for (const [id, exp] of expected) {
  const actual = generatedById.get(id)
  if (!actual) {
    errors.push(`missing generated crop ${id}`)
    continue
  }
  for (const field of ['parentId','parentPath','sourceGroupId','issueSlug','label']) {
    if (actual[field] !== exp[field]) errors.push(`${id}: ${field} mismatch`)
  }
  if (JSON.stringify(actual.box) !== JSON.stringify(exp.box)) errors.push(`${id}: pixel box mismatch`)
  if (actual.trainingEligible !== false) errors.push(`${id}: reference crop must remain trainingEligible=false`)
}
for (const id of generatedById.keys()) if (!expected.has(id)) errors.push(`unexpected generated crop ${id}`)

const expectedSourceGroups = new Set([...expected.values()].map((row) => row.sourceGroupId)).size
if (cropManifest.recordCount !== expected.size) errors.push(`crop manifest recordCount ${cropManifest.recordCount} != expected ${expected.size}`)
if (generated.length !== expected.size) errors.push(`generated records ${generated.length} != expected ${expected.size}`)
if (cropManifest.manualCropCount !== manual.length) errors.push(`manualCropCount ${cropManifest.manualCropCount} != ${manual.length}`)
if (cropManifest.gridDerivedCropCount !== gridDerivedCount) errors.push(`gridDerivedCropCount ${cropManifest.gridDerivedCropCount} != ${gridDerivedCount}`)
if (cropManifest.sourceGroupCount !== expectedSourceGroups) errors.push(`sourceGroupCount ${cropManifest.sourceGroupCount} != ${expectedSourceGroups}`)
if (cropManifest.trainingEligibleCount !== 0) errors.push('crop manifest trainingEligibleCount must remain zero')

if (releaseManifest.referencePanelCropCount !== expected.size) errors.push('release manifest referencePanelCropCount mismatch')
if (releaseManifest.referenceManualCropCount !== manual.length) errors.push('release manifest referenceManualCropCount mismatch')
if (releaseManifest.referenceGridDerivedCropCount !== gridDerivedCount) errors.push('release manifest referenceGridDerivedCropCount mismatch')
if (releaseManifest.referencePanelCropSourceGroupCount !== expectedSourceGroups) errors.push('release manifest referencePanelCropSourceGroupCount mismatch')
if (releaseManifest.totalPersistedReferenceImageFiles !== releaseManifest.localReferenceImageBinaryCount + expected.size) errors.push('release manifest totalPersistedReferenceImageFiles mismatch')

if (errors.length) {
  console.error(`REFERENCE CROP GEOMETRY VALIDATION FAILED (${errors.length})`)
  for (const error of errors) console.error(`- ${error}`)
  process.exit(1)
}

console.log(JSON.stringify({
  ok: true,
  manualCrops: manual.length,
  gridDefinitions: grids.length,
  gridDerivedCrops: gridDerivedCount,
  totalCrops: expected.size,
  sourceGroups: expectedSourceGroups,
  persistedOriginals: releaseManifest.localReferenceImageBinaryCount,
  totalPersistedReferenceImages: releaseManifest.totalPersistedReferenceImageFiles,
  trainingEligibleCrops: cropManifest.trainingEligibleCount,
}, null, 2))
