export interface ControlledEvidenceRecord {
  evidence_id: string
  dataset_id?: string
  canonical_id: string
  canonical_label: string
  cannabis_specific: boolean
  confirmation_level?: string
  reuse_status?: string
  source_url?: string
  notes?: string
}

export interface ControlledInterventionRecord {
  intervention_id: string
  canonical_label: string
  evidence_strength: string
  action: string
  regulatory_check_required?: boolean
}

export interface CanonicalEvidenceBundle {
  canonical_id: string
  canonical_label: string
  evidence: ControlledEvidenceRecord[]
  interventions: ControlledInterventionRecord[]
  hard_differentials: Record<string, unknown>[]
}

export interface EvidenceIndex {
  version: string
  generated_from_registry_sha256?: string
  by_canonical_id: Record<string, CanonicalEvidenceBundle>
}

export function evidenceFor(index: EvidenceIndex, canonicalId: string) {
  return index.by_canonical_id[canonicalId] ?? null
}

export function requireGroundedEvidence(index: EvidenceIndex, canonicalId: string) {
  const entry = evidenceFor(index, canonicalId)
  if (!entry) throw new Error(`Unknown canonical diagnosis: ${canonicalId}`)
  if (!entry.evidence.length) throw new Error(`No controlled evidence is mapped to ${canonicalId}`)
  return entry
}

export function rankEvidence(records: ControlledEvidenceRecord[]) {
  const score = (record: ControlledEvidenceRecord) => {
    let value = record.cannabis_specific ? 20 : 0
    const confirmation = (record.confirmation_level ?? '').toLowerCase()
    if (confirmation.includes('gold') || confirmation.includes('molecular') || confirmation.includes('causal')) value += 20
    else if (confirmation.includes('high')) value += 12
    if ((record.reuse_status ?? '').toLowerCase().includes('reference_only')) value -= 1
    return value
  }
  return [...records].sort((a, b) => score(b) - score(a))
}
