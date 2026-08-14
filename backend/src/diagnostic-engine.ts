import responsePolicies from '../config/diagnostic-response-policy.json'
import { requireGroundedEvidence, type EvidenceIndex } from './evidence-index'

export interface Candidate {
  canonical_id: string
  canonical_label: string
  calibrated_score: number
  reasons: string[]
}

export interface DifferentialCheck {
  unresolved: boolean
  missing_evidence?: string[]
  contradictions?: string[]
}

export interface ThreePassInput {
  pass1_candidates: Candidate[]
  pass2_evidence_ids: string[]
  differential_checks: DifferentialCheck[]
  open_set_unknown_score: number
}

function policyFor(canonicalId: string) {
  return (responsePolicies as any[]).find((p) => p.canonical_ids?.includes(canonicalId))
    ?? (responsePolicies as any[]).find((p) => p.policy_id === 'POL-DEFAULT')
}

export function adjudicate(index: EvidenceIndex, input: ThreePassInput) {
  if (!input.pass1_candidates.length) throw new Error('No pass-1 candidates')
  const ranked = [...input.pass1_candidates].sort((a, b) => b.calibrated_score - a.calibrated_score)
  const top = ranked[0]

  const evidence = requireGroundedEvidence(index, top.canonical_id)
  const policy: any = policyFor(top.canonical_id)
  const ceiling = Number(policy?.photo_only_max_confidence ?? 0.8)
  const unresolved = input.differential_checks.some((x) => x.unresolved || (x.contradictions?.length ?? 0) > 0)
  const unknown = input.open_set_unknown_score >= 0.55
  const requestedEvidence = [...new Set(input.differential_checks.flatMap((x) => x.missing_evidence ?? []))]

  let finalConfidence = Math.min(top.calibrated_score, ceiling)
  if (unresolved || unknown) finalConfidence = Math.min(finalConfidence, 0.59)

  return {
    primary: top,
    alternatives: ranked.slice(1, 4),
    final_confidence: finalConfidence,
    provisional: unresolved || unknown || policy?.photo_can_confirm === false,
    response_policy_id: policy?.policy_id ?? 'POL-DEFAULT',
    requested_evidence: requestedEvidence,
    controlled_evidence: evidence.evidence,
    pass2_evidence_ids: input.pass2_evidence_ids,
  }
}
