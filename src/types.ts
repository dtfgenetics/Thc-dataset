export type View = 'diagnose' | 'issues' | 'references' | 'log' | 'coverage' | 'about'

export type IssueCategory =
  | 'Nutrient deficiency'
  | 'Nutrient toxicity'
  | 'Insect'
  | 'Mite'
  | 'Fungal pathogen'
  | 'Oomycete pathogen'
  | 'Bacterial pathogen'
  | 'Root pathogen'
  | 'Viroid'
  | 'Virus'
  | 'Phytoplasma / Spiroplasma'
  | 'Genetic / developmental'
  | 'Environmental stress'
  | 'Water / root-zone'
  | 'Normal development'
  | 'Insufficient evidence'

export type Severity = 'low' | 'moderate' | 'high' | 'critical'
export type ReviewStatus = 'reviewed' | 'provisional' | 'incomplete'

export interface SourceRecord {
  title: string
  organization: string
  url: string
  year?: number
  authors?: string[]
  publisher?: string
  publicationDate?: string
  accessedDate: string
  doi?: string
  supportedClaims: string[]
}

export interface MediaRecord {
  id: string
  url?: string
  thumbnailUrl?: string
  alt: string
  caption: string
  creator?: string
  license?: string
  sourceUrl?: string
  mediaType: 'image' | 'video'
  requiredAttribution: string
  diagnosticLabel: string
  hostSpecies: string
  hostContext: 'cannabis' | 'non-cannabis' | 'organism-only'
  useLimitations: string[]
  displayPermission: 'permitted' | 'not-permitted' | 'unknown'
  reviewStatus: 'candidate' | 'license-review' | 'scientific-review' | 'approved-reference' | 'approved-training' | 'rejected'
  trainingPermission: 'permitted' | 'not-permitted' | 'unknown'
  sha256?: string
  perceptualHash?: string
  width?: number
  height?: number
  view: 'whole-plant' | 'close-up' | 'underside' | 'root-crown' | 'microscope' | 'diagram'
  stage?: string
  severity?: string
  confirmation: 'visual' | 'expert-reviewed' | 'lab-confirmed' | 'illustrative'
  trainingEligible: boolean
}

export interface IssueRecord {
  id: string
  slug: string
  name: string
  scientificName?: string
  canonicalId?: string
  canonicalLabel?: string
  evidenceIds?: string[]
  interventionEvidenceIds?: string[]
  responsePolicyId?: string
  photoOnlyMaxConfidence?: number
  category: IssueCategory
  severity: Severity
  reviewStatus: ReviewStatus
  summary: string
  affectedParts: string[]
  stages: string[]
  indicators: string[]
  exclusions: string[]
  progression: { stage: string; description: string }[]
  lookAlikes: string[]
  confirmation: string[]
  immediateActions: string[]
  correctivePlan: string[]
  prevention: string[]
  warnings: string[]
  sources: SourceRecord[]
  media: MediaRecord[]
}

export interface EvidenceFile {
  id: string
  file: File
  previewUrl: string
  slot: EvidenceSlot
  width?: number
  height?: number
  quality: 'checking' | 'good' | 'review'
  notes: string[]
}

export type EvidenceSlot = 'whole-plant' | 'close-up' | 'underside' | 'root-crown' | 'video'

export interface GrowContext {
  stage: string
  medium: string
  ph: string
  ec: string
  watering: string
  recentChanges: string
  symptoms: string[]
}

export interface Differential {
  issue: IssueRecord
  confidence: 'Low' | 'Moderate' | 'High'
  score: number
  supporting: string[]
  contradicting: string[]
  missing: string[]
}

export interface GrowLogEntry {
  id: string
  createdAt: string
  plantName: string
  note: string
  outcome: string
}
