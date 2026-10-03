import fs from 'node:fs'

const files = {
  editor: fs.readFileSync('src/components/ImageDetailEditor.tsx','utf8'),
  uploader: fs.readFileSync('src/components/EvidenceUploader.tsx','utf8'),
  app: fs.readFileSync('src/App.tsx','utf8'),
  observations: fs.readFileSync('src/lib/visual-observations.ts','utf8'),
  types: fs.readFileSync('src/types.ts','utf8'),
  styles: fs.readFileSync('src/styles.css','utf8'),
}

function ok(value, message) { if (!value) throw new Error(message) }

for (const marker of [
  'Derived analysis view',
  'The original upload is always retained',
  'Use detail for analysis',
  'never replaces the original image as source context or ground truth',
  'canvas.toBlob',
  'Rotate +90°',
]) ok(files.editor.includes(marker), `image detail editor missing: ${marker}`)

for (const marker of ['analysisFile?: File','analysisPreviewUrl?: string','analysisTransform?:']) {
  ok(files.types.includes(marker), `evidence contract missing: ${marker}`)
}

ok(files.observations.includes("item.analysisFile ? [item.file, item.analysisFile] : [item.file]"), 'visual analysis must send original plus derived detail')
ok(files.app.includes('URL.revokeObjectURL(item.analysisPreviewUrl)'), 'derived preview URLs must be revoked')
ok(files.uploader.includes('Use original for analysis'), 'learner must be able to return to original analysis view')
ok(files.uploader.includes('Derived detail active · original retained'), 'UI must disclose derived view state')
ok(files.styles.includes('@media (max-width:640px)'), 'detail editor must include mobile layout')
ok(files.styles.includes('100dvh'), 'detail editor must use dynamic viewport height')

console.log('Diagnostic image preprocessing contract passed.')
