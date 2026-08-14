import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const expectedIds = ['DS-137','DS-138','DS-139','DS-140','DS-141','DS-142','DS-143','DS-144','DS-145','DS-146']

function fail(message) {
  console.error(`transfer-policy validation failed: ${message}`)
  process.exitCode = 1
}

function requireText(value, label) {
  if (typeof value !== 'string' || !value.trim()) fail(`missing ${label}`)
}

function validateFile(filePath) {
  const data = JSON.parse(fs.readFileSync(filePath, 'utf8'))
  const ids = data?.scope?.datasetIds
  if (!Array.isArray(ids)) return fail(`${filePath}: scope.datasetIds must be an array`)
  if (JSON.stringify(ids) !== JSON.stringify(expectedIds)) fail(`${filePath}: expected DS-137 through DS-146 in fixed order`)

  const inv = data.invariants ?? {}
  if (inv.cannabisCausalGroundTruth !== false) fail(`${filePath}: cross-crop data must not be Cannabis causal ground truth`)
  if (inv.preserveOriginalSourceLabels !== true) fail(`${filePath}: original source labels must be preserved`)
  if (inv.requireCannabisSpecificConfirmationForCannabisEtiology !== true) fail(`${filePath}: Cannabis etiology requires Cannabis-specific confirmation`)
  if (inv.requireSha256AndPerceptualDedupBeforeTraining !== true) fail(`${filePath}: SHA-256 + perceptual dedup gate required`)
  if (inv.allowIndependentSampleInflationFromDerivatives !== false) fail(`${filePath}: derivatives cannot inflate biological sample counts`)
  if (!Array.isArray(inv.allowedUses) || inv.allowedUses.length < 4) fail(`${filePath}: allowedUses incomplete`)
  if (!Array.isArray(inv.forbiddenUses) || inv.forbiddenUses.length < 4) fail(`${filePath}: forbiddenUses incomplete`)

  const rules = data.datasetRules ?? {}
  for (const id of expectedIds) {
    if (!rules[id]) fail(`${filePath}: missing datasetRules.${id}`)
    if (!Array.isArray(rules[id]?.role) || rules[id].role.length < 1) fail(`${filePath}: ${id} role missing`)
    if (!Array.isArray(rules[id]?.rules) || rules[id].rules.length < 1) fail(`${filePath}: ${id} rules missing`)
  }

  const ds140 = rules['DS-140']?.rules?.join(' ').toLowerCase() ?? ''
  if (!ds140.includes('overlap') || !ds140.includes('double-count')) fail(`${filePath}: DS-140 overlap/double-count rule missing`)

  const ds141 = rules['DS-141']?.rules?.join(' ').toLowerCase() ?? ''
  if (!ds141.includes('64') || !ds141.includes('sourcegroupid') || !ds141.includes('one split')) fail(`${filePath}: DS-141 parent/patch leakage controls incomplete`)

  const ds142 = rules['DS-142']?.rules?.join(' ').toLowerCase() ?? ''
  if (!ds142.includes('white-background') || !ds142.includes('natural-background')) fail(`${filePath}: DS-142 domain-shift controls incomplete`)

  const ds146 = rules['DS-146']
  if (!Array.isArray(ds146?.beneficialClasses) || ds146.beneficialClasses.length < 3) fail(`${filePath}: DS-146 beneficial classes incomplete`)
  const beneficial = ds146?.beneficialClasses?.join(' ').toLowerCase() ?? ''
  for (const expected of ['lacewing','hoverfly','lady beetle']) if (!beneficial.includes(expected)) fail(`${filePath}: DS-146 missing beneficial ${expected}`)
  const ds146Rules = ds146?.rules?.join(' ').toLowerCase() ?? ''
  if (!ds146Rules.includes('hard negatives') || !ds146Rules.includes('harmful-insect')) fail(`${filePath}: DS-146 hard-negative rule missing`)

  requireText(data.policyVersion, `${filePath}: policyVersion`)
  console.log(`${path.basename(filePath)}: transfer policy validated for ${expectedIds.length} datasets`)
}

const files = process.argv.slice(2)
if (!files.length) {
  console.error('usage: node scripts/validate-transfer-policy.mjs <policy.json> [...]')
  process.exit(2)
}
for (const file of files) validateFile(file)
if (process.exitCode) process.exit(process.exitCode)
