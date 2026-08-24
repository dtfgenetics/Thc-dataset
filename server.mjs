import { createServer } from 'node:http'
import { createReadStream, existsSync, statSync } from 'node:fs'
import { extname, join, normalize, resolve } from 'node:path'

const port = Number(process.env.PORT || 4173)
const root = resolve('dist')

const mimeTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
}

function safePath(urlPath) {
  const cleanPath = decodeURIComponent(urlPath.split('?')[0] || '/')
  const requested = normalize(cleanPath).replace(/^\.\.(\/|\\|$)/, '')
  const filePath = join(root, requested === '/' ? 'index.html' : requested)
  return filePath.startsWith(root) ? filePath : join(root, 'index.html')
}

const server = createServer((request, response) => {
  if (!existsSync(root)) {
    response.writeHead(500, { 'content-type': 'text/plain; charset=utf-8' })
    response.end('Build output not found. Run npm run build before npm start.')
    return
  }

  let filePath = safePath(request.url || '/')
  if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
    filePath = join(root, 'index.html')
  }

  const type = mimeTypes[extname(filePath)] || 'application/octet-stream'
  response.writeHead(200, { 'content-type': type })
  createReadStream(filePath).pipe(response)
})

server.listen(port, '0.0.0.0', () => {
  console.log(`THC Grow Doc serving ${root} on port ${port}`)
})
