import http from 'node:http'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..', '..')
const indexPath = path.join(repoRoot, 'dataset', 'catalog', 'reference-image-index.json')
const port = Number(process.env.REFERENCE_PORT || 4171)

const normalize = (value = '') => value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

async function loadIndex() {
  const raw = await readFile(indexPath, 'utf8')
  return JSON.parse(raw)
}

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  })
  response.end(JSON.stringify(payload, null, 2))
}

const server = http.createServer(async (request, response) => {
  if (request.method === 'OPTIONS') {
    response.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    })
    response.end()
    return
  }

  const url = new URL(request.url, 'http://localhost')

  if (url.pathname === '/health') {
    sendJson(response, 200, { ok: true, service: 'reference-search-api', generatedAt: new Date().toISOString() })
    return
  }

  if (url.pathname === '/search') {
    try {
      const payload = await loadIndex()
      const query = normalize(url.searchParams.get('q') ?? '')
      const limit = Number(url.searchParams.get('limit') ?? '12') || 12

      const matches = !query
        ? payload.images.slice(0, limit)
        : payload.images.filter((entry) => {
            const haystack = normalize([
              entry.datasetId,
              entry.filename,
              entry.folder,
              entry.path,
              entry.searchText,
              entry.sha256,
              ...(entry.labels ?? []),
            ].join(' '))
            return haystack.includes(query)
          }).slice(0, limit)

      sendJson(response, 200, {
        count: matches.length,
        total: payload.images.length,
        query,
        results: matches,
      })
      return
    } catch (error) {
      sendJson(response, 500, { error: error.message })
      return
    }
  }

  if (url.pathname === '/datasets') {
    try {
      const payload = await loadIndex()
      const datasets = [...new Set(payload.images.map((entry) => entry.datasetId).filter(Boolean))].sort()
      sendJson(response, 200, { count: datasets.length, datasets })
      return
    } catch (error) {
      sendJson(response, 500, { error: error.message })
      return
    }
  }

  sendJson(response, 404, { error: 'Not found' })
})

server.listen(port, () => {
  console.log(`Reference search API listening on http://localhost:${port}`)
})
