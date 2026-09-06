import type { CaseTrendSummary, Differential, GrowContext, GrowLogEntry } from '../types'

const numberFrom = (value?: string) => {
  if (!value) return undefined
  const parsed = Number.parseFloat(value.replace(/[^0-9.+-]/g, ''))
  return Number.isFinite(parsed) ? parsed : undefined
}

const normalise = (value: string) => value.trim().toLowerCase()

function latestComparable(history: GrowLogEntry[], key: 'ph' | 'ec') {
  return [...history]
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))
    .map((entry) => ({ value: numberFrom(entry[key]), entry }))
    .find((item) => item.value !== undefined)
}

export function summarizeCaseTrend(
  context: GrowContext,
  history: GrowLogEntry[],
  results: Differential[],
): CaseTrendSummary {
  if (!history.length) {
    return {
      trend: 'insufficient',
      changes: [],
      recommendedNextStep: results[0]?.missing[0] ?? 'Add a follow-up observation after the next meaningful plant or environment change.',
      rationale: 'There is not yet a prior follow-up record to compare against the current investigation.',
    }
  }

  const changes: string[] = []
  const latest = [...history].sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))[0]
  const currentPh = numberFrom(context.ph)
  const previousPh = latestComparable(history, 'ph')
  if (currentPh !== undefined && previousPh?.value !== undefined) {
    const delta = currentPh - previousPh.value
    if (Math.abs(delta) >= 0.1) changes.push(`pH ${delta > 0 ? 'rose' : 'fell'} ${Math.abs(delta).toFixed(1)} from the last recorded measurement`)
  }

  const currentEc = numberFrom(context.ec)
  const previousEc = latestComparable(history, 'ec')
  if (currentEc !== undefined && previousEc?.value !== undefined) {
    const delta = currentEc - previousEc.value
    if (Math.abs(delta) >= 0.1) changes.push(`EC/PPM ${delta > 0 ? 'rose' : 'fell'} ${Math.abs(delta).toFixed(1)} from the last recorded measurement`)
  }

  const previousSymptoms = new Set((latest.symptoms ?? []).map(normalise))
  const currentSymptoms = new Set(context.symptoms.map(normalise))
  const newSymptoms = context.symptoms.filter((symptom) => !previousSymptoms.has(normalise(symptom)))
  const clearedSymptoms = (latest.symptoms ?? []).filter((symptom) => !currentSymptoms.has(normalise(symptom)))
  if (newSymptoms.length) changes.push(`${newSymptoms.length} new symptom${newSymptoms.length === 1 ? '' : 's'} since the latest follow-up`)
  if (clearedSymptoms.length) changes.push(`${clearedSymptoms.length} previously recorded symptom${clearedSymptoms.length === 1 ? '' : 's'} no longer selected`)

  if (context.watering && latest.watering && normalise(context.watering) !== normalise(latest.watering)) {
    changes.push('watering or substrate-moisture context changed')
  }
  if (context.stage && latest.stage && normalise(context.stage) !== normalise(latest.stage)) {
    changes.push(`stage changed from ${latest.stage} to ${context.stage}`)
  }

  const recentOutcomes = history.slice(0, 3).map((entry) => normalise(entry.outcome))
  let trend: CaseTrendSummary['trend'] = 'stable'
  if (recentOutcomes.includes('worsening') && recentOutcomes.includes('improving')) trend = 'mixed'
  else if (recentOutcomes[0] === 'worsening') trend = 'worsening'
  else if (recentOutcomes[0] === 'improving' || recentOutcomes[0] === 'resolved') trend = 'improving'
  else if (!changes.length && recentOutcomes.every((outcome) => outcome === 'monitoring')) trend = 'insufficient'

  const top = results[0]
  const runnerUp = results[1]
  let recommendedNextStep = top?.missing[0] ?? top?.issue.confirmation[0] ?? 'Capture a consistent whole-plant and affected-tissue follow-up set.'
  let rationale = top
    ? `This is the highest-value missing evidence for the current leading hypothesis, ${top.issue.name}.`
    : 'The current evidence does not yet support a ranked differential, so add a discriminating observation rather than guessing.'

  if (top && runnerUp && top.score - runnerUp.score < 2) {
    recommendedNextStep = top.missing.find((item) => item.includes('discriminating')) ?? top.issue.confirmation[0] ?? runnerUp.issue.confirmation[0] ?? recommendedNextStep
    rationale = `The leading hypotheses are close (${top.issue.name} vs ${runnerUp.issue.name}); prioritize evidence that separates those two explanations.`
  }

  return { trend, changes, recommendedNextStep, rationale }
}
