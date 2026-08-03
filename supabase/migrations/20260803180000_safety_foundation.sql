-- Janani AI safety foundation.
-- Direct client access is intentionally denied: RLS is enabled and no user policies
-- are created in this phase. Trusted backend service access will be designed separately.

create extension if not exists pgcrypto;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'safety_rule_status') then
    create type public.safety_rule_status as enum (
      'draft',
      'under_review',
      'approved',
      'retired'
    );
  end if;
end
$$;

create table if not exists public.safety_rule_versions (
  id uuid primary key default gen_random_uuid(),
  rule_id text not null,
  version text not null,
  status public.safety_rule_status not null default 'draft',
  severity text not null,
  definition jsonb not null,
  response_template text not null,
  clinician_signoff_id text,
  approved_at timestamptz,
  next_review_at timestamptz,
  created_at timestamptz not null default now(),
  unique (rule_id, version),
  constraint approved_rule_requires_signoff check (
    status <> 'approved'
    or (clinician_signoff_id is not null and approved_at is not null)
  )
);

create table if not exists public.safety_audit_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  request_id uuid not null,
  ruleset_version text not null,
  triggered_rule_ids text[] not null default '{}',
  severity text not null,
  blocks_llm boolean not null,
  synthetic boolean not null default true,
  created_at timestamptz not null default now()
);

alter table public.safety_rule_versions enable row level security;
alter table public.safety_audit_events enable row level security;

comment on table public.safety_rule_versions is
  'Versioned deterministic safety rules; approval requires clinician sign-off metadata.';
comment on table public.safety_audit_events is
  'Minimal safety-path audit events. Raw symptom text and model prompts are excluded.';
