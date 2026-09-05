import fs from 'node:fs'

const files = {
  appShell: fs.readFileSync('src/components/AppShell.tsx', 'utf8'),
  main: fs.readFileSync('src/main.tsx', 'utf8'),
  visual: fs.readFileSync('src/growdoc-visual-system-v3.css', 'utf8'),
  secondary: fs.readFileSync('src/growdoc-secondary-views-v3.css', 'utf8'),
  shell: fs.readFileSync('src/growdoc-product-shell-v3.css', 'utf8'),
}

const requiredImports = [
  "./growdoc-visual-system-v3.css",
  "./growdoc-secondary-views-v3.css",
  "./growdoc-product-shell-v3.css",
]

const requiredSelectors = [
  '.grow-doc-hero',
  '.grow-doc-stepbar',
  '.evidence-grid',
  '.result-panel',
  '.atlas-workspace-v2',
  '.issue-row',
  '.reference-grid',
  '.coverage-summary',
  '.log-form',
  '.site-header',
]

const failures = []

for (const imported of requiredImports) {
  if (!files.main.includes(imported)) failures.push(`Missing final visual import: ${imported}`)
}

const css = `${files.visual}\n${files.secondary}\n${files.shell}`
for (const selector of requiredSelectors) {
  if (!css.includes(selector)) failures.push(`Missing visual-system selector: ${selector}`)
}

if (!css.includes('@media')) failures.push('Responsive media rules are missing from the final visual system.')
if (!css.includes('max-width: 760px') && !css.includes('max-width:760px')) failures.push('Expected mobile breakpoint at 760px is missing.')
if (!css.includes('max-width: 1180px') && !css.includes('max-width:1180px')) failures.push('Expected desktop-to-tablet breakpoint at 1180px is missing.')
if (!css.includes('overflow-x')) failures.push('No explicit horizontal-overflow containment is present in the final visual CSS.')

for (const prototypeLabel of ['Dataset v0.2', 'App 0.2.0', 'Schema 1.0']) {
  if (files.appShell.includes(prototypeLabel)) failures.push(`Prototype-facing label is still public: ${prototypeLabel}`)
}

if (!files.appShell.includes('Evidence coverage')) failures.push('Public shell must expose user-facing Evidence coverage language.')
if (!files.appShell.includes('Evidence-guided screening')) failures.push('Public footer must retain the evidence-guided screening disclaimer.')

if (failures.length) {
  console.error('Grow Doc visual contract failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('Grow Doc visual contract passed.')
console.log(`Checked ${requiredImports.length} final visual imports and ${requiredSelectors.length} key product surfaces.`)
