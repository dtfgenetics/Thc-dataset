import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const required = ['sheetRow','order','datasetId','dataset','canonicalSource','version','expectedPackage','repositoryChecksum','license','destination','acquisitionStatus','integrityStatus','rightsStatus','criticalNotes','driveFolderId']

function fail(message) {
  console.error(`acquisition-snapshot validation failed: ${message}`)
  process.exitCode = 1
}

function validateFile(filePath) {
  const data = JSON.parse(fs.readFileSync(filePath, 'utf8'))
  if (!Array.isArray(data.records)) return fail(`${filePath}: records must be an array`)
  if (data.recordCount !== data.records.length) fail(`${filePath}: recordCount=${data.recordCount} but found ${data.records.length}`)
  const ids = new Set()
  const folders = new Set()
  for (const [index, row] of data.records.entries()) {
    for (const field of required) if (row[field] === undefined || row[field] === null || String(row[field]).trim() === '') fail(`${filePath}: record ${index + 1} missing ${field}`)
    if (!/^DS-\d{3,}$/.test(row.datasetId ?? '')) fail(`${filePath}: invalid datasetId ${row.datasetId}`)
    if (ids.has(row.datasetId)) fail(`${filePath}: duplicate datasetId ${row.datasetId}`)
    ids.add(row.datasetId)
    if (folders.has(row.driveFolderId)) fail(`${filePath}: duplicate Drive folder ${row.driveFolderId}`)
    folders.add(row.driveFolderId)
    try { new URL(row.canonicalSource) } catch { fail(`${filePath}: ${row.datasetId} invalid canonicalSource`) }

    const rights = `${row.license} ${row.rightsStatus}`.toLowerCase()
    const dest = String(row.destination).toLowerCase()
    const status = String(row.acquisitionStatus).toLowerCase()
    const integrity = String(row.integrityStatus).toLowerCase()
    const restricted = /noncommercial|non-commercial|sharealike|share-alike|rights verify|license verify|per-item|per-media|gate|required/.test(rights)
    if (dest.startsWith('01_raw_open') && restricted) fail(`${filePath}: ${row.datasetId} restricted/uncertain rights cannot be in open raw lane`)
    if (status.includes('quarantine') && !dest.includes('quarantine')) fail(`${filePath}: ${row.datasetId} quarantine status requires quarantine destination`)
    if (status.includes('runtime') && status.includes('blocked') && /(verified|complete|passed|ready)/.test(integrity) && !integrity.includes('pending')) fail(`${filePath}: ${row.datasetId} runtime-blocked source cannot claim completed integrity`)
  }
  console.log(`${path.basename(filePath)}: ${data.records.length} acquisition records validated`)
}

const files = process.argv.slice(2)
if (!files.length) {
  console.error('usage: node scripts/validate-acquisition-snapshot.mjs <snapshot.json> [...]')
  process.exit(2)
}
for (const file of files) validateFile(file)
if (process.exitCode) process.exit(process.exitCode)
