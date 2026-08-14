-- THC Plant Diagnostic backend schema v0.3
-- PostgreSQL-oriented starter schema. Use migrations in production.

create table if not exists diagnostic_cases (
  case_id text primary key,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  user_id text,
  external_review_consent boolean not null default false,
  training_opt_in boolean not null default false,
  status text not null default 'open'
);

create table if not exists case_media (
  media_id text primary key,
  case_id text not null references diagnostic_cases(case_id),
  media_type text not null check (media_type in ('image','video')),
  original_uri text not null,
  normalized_uri text,
  parent_media_id text references case_media(media_id),
  video_timestamp_seconds double precision,
  view_type text,
  sha256 text,
  perceptual_hash text,
  quality_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_case_media_case on case_media(case_id);
create index if not exists idx_case_media_sha256 on case_media(sha256);
create index if not exists idx_case_media_phash on case_media(perceptual_hash);

create table if not exists inference_analyses (
  analysis_id text primary key,
  case_id text not null references diagnostic_cases(case_id),
  supersedes_analysis_id text references inference_analyses(analysis_id),
  model_versions jsonb not null,
  taxonomy_version text not null,
  evidence_index_version text not null,
  decision_log jsonb not null,
  final_response jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_analyses_case on inference_analyses(case_id);

create table if not exists expert_reviews (
  review_id text primary key,
  case_id text not null references diagnostic_cases(case_id),
  analysis_id text references inference_analyses(analysis_id),
  escalation_id text not null,
  reviewer_id text,
  review_status text not null,
  final_labels jsonb,
  evidence_json jsonb,
  corrective_action_json jsonb,
  uncertainty_notes text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists case_messages (
  message_id text primary key,
  case_id text not null references diagnostic_cases(case_id),
  role text not null check (role in ('user','reviewer','system')),
  message text not null,
  reviewer_id text,
  created_at timestamptz not null default now()
);

create index if not exists idx_case_messages_case on case_messages(case_id, created_at);

create table if not exists intervention_outcomes (
  outcome_id text primary key,
  case_id text not null references diagnostic_cases(case_id),
  analysis_id text references inference_analyses(analysis_id),
  intervention_ids text[] not null default '{}',
  started_at timestamptz,
  reported_at timestamptz not null default now(),
  outcome text check (outcome in ('better','same','worse','unknown')),
  side_effects text,
  notes text
);

-- Invariants:
-- 1. Never overwrite an inference_analyses.final_response after human review.
-- 2. Store a revised model/reviewer result as a new analysis_id with supersedes_analysis_id.
-- 3. Training export requires explicit training_opt_in plus evidence-supported final labels and rights gates.
-- 4. Locked evaluation/benchmark cases must never enter training.
