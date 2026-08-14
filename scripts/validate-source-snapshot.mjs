import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const required = [
  'id', 'name', 'domain', 'cannabisSpecific', 'modality', 'primaryTask',
  'license', 'academicUse', 'rawRedistribution', 'publicModelDeployment',
  'priority', 'sourceUrl', 'provenanceStatus'
]

function fail(message) {
  console.error(`source-snapshot validation failed: ${message}`)
  process.exitCode = 1
}

function validateFile(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8')
  const data = JSON.parse(raw)
  if (!Array.isArray(data.records)) {
    fail(`${filePath}: records must be an array`)
    return
  }

  const ids = new Set()
  for (const [index, row] of data.records.entries()) {
    for (const field of required) {
      if (row[field] === undefined || row[field] === null || String(row[field]).trim() === '') {
        fail(`${filePath}: record ${index + 1} missing ${field}`)
      }
    }

    if (!/^DS-\d{3,}$/.test(row.id ?? '')) fail(`${filePath}: invalid dataset id ${row.id}`)
    if (ids.has(row.id)) fail(`${filePath}: duplicate dataset id ${row.id}`)
    ids.add(row.id)

    if (!['YES', 'NO', 'PARTIAL'].includes(row.cannabisSpecific)) {
      fail(`${filePath}: ${row.id} invalid cannabisSpecific=${row.cannabisSpecific}`)
    }
    if (!['P0', 'P1', 'P2', 'P3'].includes(row.priority)) {
      fail(`${filePath}: ${row.id} invalid priority=${row.priority}`)
    }
    try {
      new URL(row.sourceUrl)
    } catch {
      fail(`${filePath}: ${row.id} invalid sourceUrl=${row.sourceUrl}`)
    }

    const rightsText = `${row.license} ${row.academicUse} ${row.rawRedistribution} ${row.publicModelDeployment}`.toLowerCase()
    if (rightsText.includes('unknown') && !String(row.provenanceStatus).toLowerCase().includes('verify')) {
      fail(`${filePath}: ${row.id} has unknown rights but provenanceStatus does not require verification`)
    }
  }

  console.log(`${path.basename(filePath)}: ${data.records.length} records validated`)
}

const files = process.argv.slice(2)
if (!files.length) {
  console.error('usage: node scripts/validate-source-snapshot.mjs <snapshot.json> [...]')
  process.exit(2)
}

for (const file of files) validateFile(file)
if (process.exitCode) process.exit(process.exitCode)
