import { copyFileSync, mkdirSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const rootDir = fileURLToPath(new URL('.', import.meta.url))

type OriginalManifest = { records: Array<{ repository_path: string }> }
type CropManifest = { records: Array<{ repositoryPath: string }> }

function publishReferenceMedia(): Plugin {
  return {
    name: 'grow-doc-publish-reference-media',
    apply: 'build',
    closeBundle() {
      const originalManifest = JSON.parse(readFileSync(resolve(rootDir, 'images/reference/manifest.json'), 'utf8')) as OriginalManifest
      const cropManifest = JSON.parse(readFileSync(resolve(rootDir, 'images/reference/crops-manifest.json'), 'utf8')) as CropManifest
      const repositoryPaths = new Set([
        ...originalManifest.records.map((record) => record.repository_path),
        ...cropManifest.records.map((record) => record.repositoryPath),
      ])

      for (const repositoryPath of repositoryPaths) {
        const relativePath = repositoryPath.replace(/^images\/reference\//, '')
        const source = resolve(rootDir, repositoryPath)
        const destination = resolve(rootDir, 'dist/reference-media', relativePath)
        mkdirSync(dirname(destination), { recursive: true })
        copyFileSync(source, destination)
      }

      console.log(`[grow-doc] published ${repositoryPaths.size} persisted reference assets`)
    },
  }
}

export default defineConfig({
  base: '/thc-grow-doc/',
  plugins: [react(), publishReferenceMedia()],
  build: {
    outDir: 'dist',
    sourcemap: true,
    assetsDir: 'assets',
  },
})
