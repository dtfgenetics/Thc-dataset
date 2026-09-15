import fs from 'node:fs'

const files = {
  app: fs.readFileSync('src/App.tsx', 'utf8'),
  appShell: fs.readFileSync('src/components/AppShell.tsx', 'utf8'),
  evidenceUploader: fs.readFileSync('src/components/EvidenceUploader.tsx', 'utf8'),
  growContext: fs.readFileSync('src/components/GrowContextForm.tsx', 'utf8'),
  diagnosticResult: fs.readFileSync('src/components/DiagnosticResult.tsx', 'utf8'),
  main: fs.readFileSync('src/main.tsx', 'utf8'),
  production: fs.readFileSync('src/growdoc-production.css', 'utf8'),
}

const failures = []

const requiredImports = [
  "./styles.css",
  "./visual-observations.css",
  "./growdoc-production.css",
]

for (const imported of requiredImports) {
  if (!files.main.includes(imported)) failures.push(`Missing production visual import: ${imported}`)
}

const retiredRuntimeImports = [
  './growdoc-visual-polish.css',
  './growdoc-visual-polish-views.css',
  './growdoc-mobile-containment.css',
  './growdoc-visual-system-v3.css',
  './growdoc-secondary-views-v3.css',
  './growdoc-shell-v3.css',
  './growdoc-mobile-render-refinement-v1.css',
  './growdoc-visual-pass-2.css',
]

for (const retired of retiredRuntimeImports) {
  if (files.main.includes(retired) || files.app.includes(retired)) failures.push(`Legacy visual override is still active: ${retired}`)
}

const requiredSelectors = [
  '.site-header',
  '.desktop-nav',
  '.mobile-nav',
  '.grow-doc-hero',
  '.grow-doc-stepbar',
  '.diagnostic-layout',
  '.primary-evidence-grid',
  '.optional-evidence',
  '.context-disclosure',
  '.result-panel',
  '.action-plan',
  '.technical-details',
  '.view-container',
]

for (const selector of requiredSelectors) {
  if (!files.production.includes(selector)) failures.push(`Missing production visual-system selector: ${selector}`)
}

if (!files.production.includes('@media')) failures.push('Responsive media rules are missing from the production visual system.')
if (!files.production.includes('max-width: 820px')) failures.push('Expected primary mobile/tablet breakpoint at 820px is missing.')
if (!files.production.includes('max-width: 560px')) failures.push('Expected compact mobile breakpoint at 560px is missing.')
if (!files.production.includes('min-width: 0')) failures.push('Expected grid overflow containment is missing from the production visual system.')
if (!files.production.includes('prefers-reduced-motion')) failures.push('Reduced-motion accessibility handling is missing.')

for (const prototypeLabel of ['Dataset v0.2', 'App 0.2.0', 'Schema 1.0']) {
  if (files.appShell.includes(prototypeLabel)) failures.push(`Prototype-facing label is still public: ${prototypeLabel}`)
}

for (const obsoletePublicLabel of ['Evidence coverage</button>', 'Dataset health</button>']) {
  if (files.appShell.includes(obsoletePublicLabel)) failures.push(`Research/admin language is still exposed as a primary public action: ${obsoletePublicLabel}`)
}

if (!files.appShell.includes("label: 'Diagnose'")) failures.push('Primary navigation must expose Diagnose.')
if (!files.appShell.includes("label: 'Issue library'")) failures.push('Primary navigation must expose Issue library.')
if (!files.appShell.includes("label: 'Grow log'")) failures.push('Primary navigation must expose Grow log.')
if (!files.appShell.includes('Research coverage')) failures.push('Research coverage must remain accessible outside the primary navigation.')
if (!files.appShell.includes('Photo-first plant-health screening')) failures.push('Public footer must explain the photo-first screening purpose.')

if (!files.app.includes('Show us the plant. Get a clear next step.')) failures.push('Primary diagnostic hero must use grower-first task language.')
if (!files.evidenceUploader.includes('Start with a clear photo')) failures.push('Evidence intake must begin with a clear photo-first instruction.')
if (!files.evidenceUploader.includes('<details className="optional-evidence">')) failures.push('Secondary evidence views must use progressive disclosure.')
if (!files.growContext.includes('<details className="context-disclosure">')) failures.push('Optional grow context must use progressive disclosure.')
if (!files.diagnosticResult.includes('What to do now')) failures.push('Diagnostic results must surface immediate actions before technical detail.')
if (!files.diagnosticResult.includes('<details className="technical-details">')) failures.push('Technical diagnostic reasoning must be progressively disclosed.')

if (failures.length) {
  console.error('Grow Doc production visual contract failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('Grow Doc production visual contract passed.')
console.log(`Checked ${requiredImports.length} runtime imports, ${requiredSelectors.length} core surfaces, responsive behavior, hierarchy, and progressive disclosure.`)
