import fs from 'node:fs/promises'

async function json(path) {
  return JSON.parse(await fs.readFile(path, 'utf8'))
}

const [manifest, profileIndex, sources, profileMedia, trainingMedia, modelReadiness, splitManifest, referenceManifest, cropManifest] = await Promise.all([
  json('data/manifest.json'),
  json('data/profiles/index.json'),
  json('data/sources.json'),
  json('data/profile-reference-media.json'),
  json('data/training-eligible-media.json'),
  json('data/model-training-readiness.json'),
  json('data/splits/manifest.json'),
  json('images/reference/manifest.json'),
  json('images/reference/crops-manifest.json'),
])

const expected = {
  profiles: profileIndex.recordCount,
  sources: sources.length,
  profileMedia: profileMedia.length,
  trainingEligible: trainingMedia.length,
  originals: referenceManifest.recordCount,
  crops: cropManifest.recordCount,
}
expected.totalReferenceImages = expected.originals + expected.crops

const errors = []
const requireEqual = (label, actual, wanted) => {
  if (actual !== wanted) errors.push(`${label}: ${actual} != ${wanted}`)
}

requireEqual('manifest.diagnosticProfileCount', manifest.diagnosticProfileCount, expected.profiles)
requireEqual('manifest.standaloneDetailedProfileCount', manifest.standaloneDetailedProfileCount, expected.profiles)
requireEqual('manifest.evidenceSourceCount', manifest.evidenceSourceCount, expected.sources)
requireEqual('manifest.profileReferenceMediaCount', manifest.profileReferenceMediaCount, expected.profileMedia)
requireEqual('manifest.trainingEligibleMediaCount', manifest.trainingEligibleMediaCount, expected.trainingEligible)
requireEqual('manifest.localReferenceImageBinaryCount', manifest.localReferenceImageBinaryCount, expected.originals)
requireEqual('manifest.referencePanelCropCount', manifest.referencePanelCropCount, expected.crops)
requireEqual('manifest.totalPersistedReferenceImageFiles', manifest.totalPersistedReferenceImageFiles, expected.totalReferenceImages)

requireEqual('modelReadiness.knowledgeLayer.diagnosticProfiles', modelReadiness.knowledgeLayer?.diagnosticProfiles, expected.profiles)
requireEqual('modelReadiness.knowledgeLayer.materializedProfiles', modelReadiness.knowledgeLayer?.materializedProfiles, expected.profiles)
requireEqual('modelReadiness.knowledgeLayer.evidenceSources', modelReadiness.knowledgeLayer?.evidenceSources, expected.sources)
requireEqual('modelReadiness.knowledgeLayer.profileLinkedReferenceMedia', modelReadiness.knowledgeLayer?.profileLinkedReferenceMedia, expected.profileMedia)
requireEqual('modelReadiness.visionLayer.referenceOriginals', modelReadiness.visionLayer?.referenceOriginals, expected.originals)
requireEqual('modelReadiness.visionLayer.referenceCrops', modelReadiness.visionLayer?.referenceCrops, expected.crops)
requireEqual('modelReadiness.visionLayer.totalReferenceImages', modelReadiness.visionLayer?.totalReferenceImages, expected.totalReferenceImages)
requireEqual('modelReadiness.visionLayer.trainingEligibleSamples', modelReadiness.visionLayer?.trainingEligibleSamples, expected.trainingEligible)

requireEqual('splitManifest.knowledgeLayerSnapshot.diagnosticProfiles', splitManifest.knowledgeLayerSnapshot?.diagnosticProfiles, expected.profiles)
requireEqual('splitManifest.knowledgeLayerSnapshot.evidenceSources', splitManifest.knowledgeLayerSnapshot?.evidenceSources, expected.sources)
requireEqual('splitManifest.knowledgeLayerSnapshot.profileLinkedReferenceMedia', splitManifest.knowledgeLayerSnapshot?.profileLinkedReferenceMedia, expected.profileMedia)
requireEqual('splitManifest.knowledgeLayerSnapshot.referenceOriginals', splitManifest.knowledgeLayerSnapshot?.referenceOriginals, expected.originals)
requireEqual('splitManifest.knowledgeLayerSnapshot.referenceCrops', splitManifest.knowledgeLayerSnapshot?.referenceCrops, expected.crops)
requireEqual('splitManifest.counts.totalTrainingEligible', Number(splitManifest.counts?.totalTrainingEligible ?? -1), expected.trainingEligible)

const splitTotal = ['train', 'validation', 'test', 'holdout'].reduce((sum, key) => sum + Number(splitManifest.counts?.[key] ?? 0), 0)
if (expected.trainingEligible === 0) {
  if (modelReadiness.readyForSupervisedCannabisDiagnosisTraining !== false) errors.push('model readiness must remain false while trainingEligible=0')
  if (splitManifest.ready !== false || splitTotal !== 0) errors.push('supervised splits must remain empty and blocked while trainingEligible=0')
}

if (errors.length) {
  console.error(`RELEASE METADATA VALIDATION FAILED (${errors.length})`)
  errors.forEach((error) => console.error(`- ${error}`))
  process.exit(1)
}

console.log(JSON.stringify({ ok: true, ...expected, splitSamples: splitTotal, supervisedTrainingReady: modelReadiness.readyForSupervisedCannabisDiagnosisTraining }, null, 2))
