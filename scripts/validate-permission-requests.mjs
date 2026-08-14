import fs from 'node:fs'
import process from 'node:process'

const allowedStatus = new Set([
  'REQUEST_DRAFT_READY',
  'READY_TO_SEND',
  'SENT',
  'RESPONSE_RECEIVED',
  'APPROVED',
  'PARTIAL_APPROVAL',
  'DECLINED',
  'CLOSED_NO_RESPONSE',
])

const allowedPriority = new Set(['P0', 'P1', 'P2', 'P3'])
const requiredFields = [
  'requestId',
  'datasetId',
  'source',
  'priority',
  'status',
  'contact',
  'requestedAssets',
  'requestedMetadata',
  'rightsRequested',
  'acquisitionRule',
  'notes',
]

function fail(message) {
  console.error(`permission-request validation failed: ${message}`)
  process.exitCode = 1
}

function validate(filePath) {
  const data = JSON.parse(fs.readFileSync(filePath, 'utf8'))
  if (!Array.isArray(data.requests)) {
    fail(`${filePath}: requests must be an array`)
    return
  }

  const requestIds = new Set()
  const datasetIds = new Set()

  for (const [index, row] of data.requests.entries()) {
    for (const field of requiredFields) {
      if (row[field] === undefined || row[field] === null || (typeof row[field] === 'string' && !row[field].trim())) {
        fail(`${filePath}: request ${index + 1} missing ${field}`)
      }
    }

    if (!/^PERM-\d{3}$/.test(row.requestId ?? '')) fail(`${filePath}: invalid requestId ${row.requestId}`)
    if (!/^DS-\d{3,}$/.test(row.datasetId ?? '')) fail(`${filePath}: invalid datasetId ${row.datasetId}`)
    if (!allowedPriority.has(row.priority)) fail(`${filePath}: ${row.requestId} invalid priority ${row.priority}`)
    if (!allowedStatus.has(row.status)) fail(`${filePath}: ${row.requestId} invalid status ${row.status}`)

    if (requestIds.has(row.requestId)) fail(`${filePath}: duplicate requestId ${row.requestId}`)
    requestIds.add(row.requestId)

    if (datasetIds.has(row.datasetId)) fail(`${filePath}: duplicate datasetId ${row.datasetId}`)
    datasetIds.add(row.datasetId)

    for (const field of ['requestedAssets', 'requestedMetadata', 'rightsRequested']) {
      if (!Array.isArray(row[field]) || row[field].length === 0) fail(`${filePath}: ${row.requestId} ${field} must be non-empty`)
    }

    if (!row.contact || typeof row.contact.nameOrOrganization !== 'string' || !row.contact.nameOrOrganization.trim()) {
      fail(`${filePath}: ${row.requestId} missing contact.nameOrOrganization`)
    }

    if (row.status === 'REQUEST_DRAFT_READY' && row.requestedDate) {
      fail(`${filePath}: ${row.requestId} is only a draft but has requestedDate=${row.requestedDate}`)
    }

    if (row.status === 'APPROVED' && !row.responseDate) {
      fail(`${filePath}: ${row.requestId} approved without responseDate`)
    }
  }

  console.log(`${filePath}: ${data.requests.length} permission requests validated`)
}

const files = process.argv.slice(2)
if (!files.length) {
  console.error('usage: node scripts/validate-permission-requests.mjs <requests.json> [...]')
  process.exit(2)
}

for (const file of files) validate(file)
if (process.exitCode) process.exit(process.exitCode)
