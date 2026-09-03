#!/usr/bin/env node
import { copyFileSync, mkdirSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('..', import.meta.url))
const originalManifest = JSON.parse(readFileSync(resolve(rootDir, 'images/reference/manifest.json'), 'utf8'))
const cropManifest = JSON.parse(readFileSync(resolve(rootDir, 'images/reference/crops-manifest.json'), 'utf8'))
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
