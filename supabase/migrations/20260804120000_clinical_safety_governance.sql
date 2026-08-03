-- Clinical safety governance foundation.
-- No end-user role may read or mutate reviewer, rule-review, or release records.

create table if not exists public.clinical_safety_reviewers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique references auth.users(id) on delete restrict,
  display_name text not null check (length(trim(display_name)) >= 2),
  role text not null check (role in ('obstetrician', 'clinical_safety', 'language_reviewer')),
  license_jurisdiction text not null check (length(trim(license_jurisdiction)) >= 2),
  license_reference text not null check (length(trim(license_reference)) >= 3),
  credential_verified_at timestamptz not null,
  credential_expires_at timestamptz not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint clinical_safety_reviewer_credential_window
    check (credential_expires_at > credential_verified_at),
  constraint clinical_safety_reviewer_license_unique
    unique (license_jurisdiction, license_reference)
);

create table if not exists public.clinical_safety_rule_candidates (
  id uuid primary key default gen_random_uuid(),
  rule_id text not null check (length(trim(rule_id)) >= 3),
  version text not null check (length(trim(version)) >= 1),
  status text not null default 'draft'
    check (status in ('draft', 'under_review', 'approved', 'retired')),
  severity text not null
    check (severity in ('routine', 'contact_clinician', 'urgent', 'emergency')),
  predicate_key text not null check (length(trim(predicate_key)) >= 3),
  clinical_rationale text not null check (length(trim(clinical_rationale)) >= 20),
  applicability jsonb not null check (jsonb_typeof(applicability) = 'object'),
  escalation_text jsonb not null check (jsonb_typeof(escalation_text) = 'object'),
  source_manifest jsonb not null check (
    jsonb_typeof(source_manifest) = 'array'
    and jsonb_array_length(source_manifest) > 0
  ),
  content_digest text not null unique check (content_digest ~ '^[0-9a-f]{64}$'),
  supersedes_version text,
  created_by uuid references public.clinical_safety_reviewers(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (rule_id, version)
);

create table if not exists public.clinical_safety_rule_reviews (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references public.clinical_safety_rule_candidates(id)
    on delete restrict,
  candidate_digest text not null check (candidate_digest ~ '^[0-9a-f]{64}$'),
  reviewer_id uuid not null references public.clinical_safety_reviewers(id)
    on delete restrict,
  reviewer_role text not null
    check (reviewer_role in ('obstetrician', 'clinical_safety', 'language_reviewer')),
  decision text not null check (decision in ('approve', 'request_changes', 'reject')),
  rationale text not null check (length(trim(rationale)) >= 10),
  reviewed_at timestamptz not null default now(),
  unique (candidate_id, candidate_digest, reviewer_id)
);

create table if not exists public.clinical_safety_releases (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references public.clinical_safety_rule_candidates(id)
    on delete restrict,
  rule_id text not null,
  rule_version text not null,
  candidate_digest text not null check (candidate_digest ~ '^[0-9a-f]{64}$'),
  status text not null default 'approved'
    check (status in ('approved', 'active', 'expired', 'retired', 'rolled_back')),
  approved_at timestamptz not null,
  activates_at timestamptz not null,
  expires_at timestamptz not null,
  supersedes_release_id uuid references public.clinical_safety_releases(id) on delete restrict,
  terminal_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint clinical_safety_release_activation_window
    check (activates_at >= approved_at and expires_at > activates_at)
);

create unique index if not exists one_active_clinical_safety_release_per_rule
on public.clinical_safety_releases (rule_id)
where status = 'active';

create table if not exists public.clinical_safety_release_approvals (
  release_id uuid not null references public.clinical_safety_releases(id) on delete restrict,
  review_id uuid not null unique references public.clinical_safety_rule_reviews(id)
    on delete restrict,
  reviewer_id uuid not null references public.clinical_safety_reviewers(id) on delete restrict,
  reviewer_role text not null
    check (reviewer_role in ('obstetrician', 'clinical_safety')),
  created_at timestamptz not null default now(),
  primary key (release_id, reviewer_id)
);

create table if not exists public.clinical_safety_governance_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null check (
    event_type in (
      'review_recorded',
      'release_approved',
      'release_activated',
      'release_retired',
      'release_rolled_back'
    )
  ),
  aggregate_type text not null check (aggregate_type in ('candidate', 'release')),
  aggregate_id uuid not null,
  actor_reviewer_id uuid references public.clinical_safety_reviewers(id) on delete restrict,
  occurred_at timestamptz not null default now(),
  reason text not null check (length(trim(reason)) >= 3),
  prior_status text,
  new_status text,
  content_digest text check (content_digest is null or content_digest ~ '^[0-9a-f]{64}$'),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object')
);

create or replace function public.set_janani_governance_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger set_clinical_safety_reviewers_updated_at
before update on public.clinical_safety_reviewers
for each row execute function public.set_janani_governance_updated_at();

create trigger set_clinical_safety_candidates_updated_at
before update on public.clinical_safety_rule_candidates
for each row execute function public.set_janani_governance_updated_at();

create trigger set_clinical_safety_releases_updated_at
before update on public.clinical_safety_releases
for each row execute function public.set_janani_governance_updated_at();

create or replace function public.prevent_janani_candidate_content_mutation()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.rule_id is distinct from old.rule_id
    or new.version is distinct from old.version
    or new.severity is distinct from old.severity
    or new.predicate_key is distinct from old.predicate_key
    or new.clinical_rationale is distinct from old.clinical_rationale
    or new.applicability is distinct from old.applicability
    or new.escalation_text is distinct from old.escalation_text
    or new.source_manifest is distinct from old.source_manifest
    or new.content_digest is distinct from old.content_digest
    or new.supersedes_version is distinct from old.supersedes_version
    or new.created_by is distinct from old.created_by
    or new.created_at is distinct from old.created_at
  then
    raise exception 'Safety rule candidate content is immutable; create a new version'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger prevent_clinical_safety_candidate_content_mutation
before update on public.clinical_safety_rule_candidates
for each row execute function public.prevent_janani_candidate_content_mutation();

create or replace function public.prevent_janani_governance_history_mutation()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  raise exception 'Clinical safety governance history is append-only'
    using errcode = '42501';
end;
$$;

create trigger prevent_clinical_safety_review_mutation
before update or delete on public.clinical_safety_rule_reviews
for each row execute function public.prevent_janani_governance_history_mutation();

create trigger prevent_clinical_safety_approval_mutation
before update or delete on public.clinical_safety_release_approvals
for each row execute function public.prevent_janani_governance_history_mutation();

create trigger prevent_clinical_safety_event_mutation
before update or delete on public.clinical_safety_governance_events
for each row execute function public.prevent_janani_governance_history_mutation();

alter table public.clinical_safety_reviewers enable row level security;
alter table public.clinical_safety_rule_candidates enable row level security;
alter table public.clinical_safety_rule_reviews enable row level security;
alter table public.clinical_safety_releases enable row level security;
alter table public.clinical_safety_release_approvals enable row level security;
alter table public.clinical_safety_governance_events enable row level security;

revoke all on table public.clinical_safety_reviewers from public, anon, authenticated;
revoke all on table public.clinical_safety_rule_candidates from public, anon, authenticated;
revoke all on table public.clinical_safety_rule_reviews from public, anon, authenticated;
revoke all on table public.clinical_safety_releases from public, anon, authenticated;
revoke all on table public.clinical_safety_release_approvals from public, anon, authenticated;
revoke all on table public.clinical_safety_governance_events from public, anon, authenticated;

grant select, insert, update on table public.clinical_safety_reviewers to service_role;
grant select, insert, update on table public.clinical_safety_rule_candidates to service_role;
grant select, insert on table public.clinical_safety_rule_reviews to service_role;
grant select, insert, update on table public.clinical_safety_releases to service_role;
grant select, insert on table public.clinical_safety_release_approvals to service_role;
grant select, insert on table public.clinical_safety_governance_events to service_role;

create or replace function public.record_janani_clinical_rule_review(
  p_review_id uuid,
  p_candidate_id uuid,
  p_reviewer_id uuid,
  p_decision text,
  p_rationale text,
  p_reviewed_at timestamptz default now()
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_candidate_digest text;
  v_candidate_status text;
  v_reviewer_role text;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if p_decision not in ('approve', 'request_changes', 'reject') then
    raise exception 'Invalid review decision' using errcode = '22023';
  end if;
  if p_rationale is null or length(trim(p_rationale)) < 10 then
    raise exception 'Review rationale must contain at least 10 characters'
      using errcode = '22023';
  end if;

  select candidate.content_digest, candidate.status
  into v_candidate_digest, v_candidate_status
  from public.clinical_safety_rule_candidates candidate
  where candidate.id = p_candidate_id;

  if v_candidate_digest is null then
    raise exception 'Safety rule candidate not found' using errcode = 'P0002';
  end if;
  if v_candidate_status not in ('draft', 'under_review') then
    raise exception 'Only draft or under-review candidates may be reviewed'
      using errcode = '42501';
  end if;

  select clinical_reviewer.role
  into v_reviewer_role
  from public.clinical_safety_reviewers clinical_reviewer
  where clinical_reviewer.id = p_reviewer_id
    and clinical_reviewer.active
    and clinical_reviewer.credential_verified_at <= p_reviewed_at
    and clinical_reviewer.credential_expires_at > p_reviewed_at;

  if v_reviewer_role is null then
    raise exception 'Reviewer credentials are not current' using errcode = '42501';
  end if;

  insert into public.clinical_safety_rule_reviews (
    id,
    candidate_id,
    candidate_digest,
    reviewer_id,
    reviewer_role,
    decision,
    rationale,
    reviewed_at
  ) values (
    p_review_id,
    p_candidate_id,
    v_candidate_digest,
    p_reviewer_id,
    v_reviewer_role,
    p_decision,
    p_rationale,
    p_reviewed_at
  );

  update public.clinical_safety_rule_candidates
  set status = 'under_review'
  where id = p_candidate_id and status = 'draft';

  insert into public.clinical_safety_governance_events (
    event_type,
    aggregate_type,
    aggregate_id,
    actor_reviewer_id,
    occurred_at,
    reason,
    prior_status,
    new_status,
    content_digest,
    metadata
  ) values (
    'review_recorded',
    'candidate',
    p_candidate_id,
    p_reviewer_id,
    p_reviewed_at,
    p_rationale,
    v_candidate_status,
    'under_review',
    v_candidate_digest,
    jsonb_build_object('review_id', p_review_id, 'decision', p_decision)
  );

  return p_review_id;
end;
$$;

create or replace function public.approve_janani_clinical_safety_release(
  p_release_id uuid,
  p_candidate_id uuid,
  p_activates_at timestamptz,
  p_expires_at timestamptz,
  p_supersedes_release_id uuid default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_candidate public.clinical_safety_rule_candidates%rowtype;
  v_source_deadline timestamptz;
  v_credential_deadline timestamptz;
  v_approval_count integer;
  v_role_count integer;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if p_activates_at < now() or p_expires_at <= p_activates_at then
    raise exception 'Invalid release activation window' using errcode = '22023';
  end if;

  select * into v_candidate
  from public.clinical_safety_rule_candidates candidate
  where candidate.id = p_candidate_id
  for update;

  if v_candidate.id is null then
    raise exception 'Safety rule candidate not found' using errcode = 'P0002';
  end if;
  if v_candidate.status <> 'under_review' then
    raise exception 'Candidate must be under review before release approval'
      using errcode = '42501';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(v_candidate.source_manifest) source_item
    where coalesce(source_item ->> 'development_placeholder', 'false') = 'true'
  ) then
    raise exception 'Development-placeholder sources cannot be approved'
      using errcode = '42501';
  end if;

  select min((source_item ->> 'expires_at')::timestamptz)
  into v_source_deadline
  from jsonb_array_elements(v_candidate.source_manifest) source_item;

  if v_source_deadline is null or v_source_deadline <= now() then
    raise exception 'Candidate contains an expired or invalid clinical source'
      using errcode = '42501';
  end if;

  if exists (
    select 1
    from public.clinical_safety_rule_reviews review
    where review.candidate_id = p_candidate_id
      and review.candidate_digest = v_candidate.content_digest
      and review.decision <> 'approve'
  ) then
    raise exception 'Every review for the candidate digest must approve release'
      using errcode = '42501';
  end if;

  select count(distinct review.reviewer_id), count(distinct review.reviewer_role)
  into v_approval_count, v_role_count
  from public.clinical_safety_rule_reviews review
  where review.candidate_id = p_candidate_id
    and review.candidate_digest = v_candidate.content_digest
    and review.decision = 'approve'
    and review.reviewer_role in ('obstetrician', 'clinical_safety');

  if v_approval_count < 2 or v_role_count < 2 then
    raise exception 'Release requires obstetrician and clinical-safety approvals'
      using errcode = '42501';
  end if;

  if not exists (
    select 1 from public.clinical_safety_rule_reviews review
    where review.candidate_id = p_candidate_id
      and review.candidate_digest = v_candidate.content_digest
      and review.decision = 'approve'
      and review.reviewer_role = 'obstetrician'
  ) or not exists (
    select 1 from public.clinical_safety_rule_reviews review
    where review.candidate_id = p_candidate_id
      and review.candidate_digest = v_candidate.content_digest
      and review.decision = 'approve'
      and review.reviewer_role = 'clinical_safety'
  ) then
    raise exception 'Required reviewer roles are missing' using errcode = '42501';
  end if;

  select min(clinical_reviewer.credential_expires_at)
  into v_credential_deadline
  from public.clinical_safety_rule_reviews review
  join public.clinical_safety_reviewers clinical_reviewer
    on clinical_reviewer.id = review.reviewer_id
  where review.candidate_id = p_candidate_id
    and review.candidate_digest = v_candidate.content_digest
    and review.decision = 'approve'
    and review.reviewer_role in ('obstetrician', 'clinical_safety')
    and clinical_reviewer.active
    and clinical_reviewer.credential_verified_at <= now()
    and clinical_reviewer.credential_expires_at > now();

  if v_credential_deadline is null then
    raise exception 'Approving reviewer credentials are not current'
      using errcode = '42501';
  end if;
  if p_expires_at > least(v_source_deadline, v_credential_deadline) then
    raise exception 'Release cannot outlive sources or reviewer credentials'
      using errcode = '42501';
  end if;

  insert into public.clinical_safety_releases (
    id,
    candidate_id,
    rule_id,
    rule_version,
    candidate_digest,
    status,
    approved_at,
    activates_at,
    expires_at,
    supersedes_release_id
  ) values (
    p_release_id,
    p_candidate_id,
    v_candidate.rule_id,
    v_candidate.version,
    v_candidate.content_digest,
    'approved',
    now(),
    p_activates_at,
    p_expires_at,
    p_supersedes_release_id
  );

  insert into public.clinical_safety_release_approvals (
    release_id,
    review_id,
    reviewer_id,
    reviewer_role
  )
  select
    p_release_id,
    review.id,
    review.reviewer_id,
    review.reviewer_role
  from public.clinical_safety_rule_reviews review
  where review.candidate_id = p_candidate_id
    and review.candidate_digest = v_candidate.content_digest
    and review.decision = 'approve'
    and review.reviewer_role in ('obstetrician', 'clinical_safety');

  update public.clinical_safety_rule_candidates
  set status = 'approved'
  where id = p_candidate_id;

  insert into public.clinical_safety_governance_events (
    event_type,
    aggregate_type,
    aggregate_id,
    occurred_at,
    reason,
    prior_status,
    new_status,
    content_digest,
    metadata
  ) values (
    'release_approved',
    'release',
    p_release_id,
    now(),
    'Dual clinical approval completed',
    null,
    'approved',
    v_candidate.content_digest,
    jsonb_build_object('candidate_id', p_candidate_id)
  );

  return p_release_id;
end;
$$;

create or replace function public.activate_janani_clinical_safety_release(
  p_release_id uuid,
  p_reason text default 'Approved release activated'
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_release public.clinical_safety_releases%rowtype;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;

  select * into v_release
  from public.clinical_safety_releases release
  where release.id = p_release_id
  for update;

  if v_release.id is null then
    raise exception 'Clinical safety release not found' using errcode = 'P0002';
  end if;
  if v_release.status <> 'approved' then
    raise exception 'Only approved releases may be activated' using errcode = '42501';
  end if;
  if now() < v_release.activates_at or now() >= v_release.expires_at then
    raise exception 'Release is outside its activation window' using errcode = '42501';
  end if;

  update public.clinical_safety_releases
  set status = 'retired', terminal_reason = 'Superseded by release ' || p_release_id::text
  where rule_id = v_release.rule_id and status = 'active' and id <> p_release_id;

  update public.clinical_safety_releases
  set status = 'active', terminal_reason = null
  where id = p_release_id;

  insert into public.clinical_safety_governance_events (
    event_type,
    aggregate_type,
    aggregate_id,
    occurred_at,
    reason,
    prior_status,
    new_status,
    content_digest
  ) values (
    'release_activated',
    'release',
    p_release_id,
    now(),
    p_reason,
    v_release.status,
    'active',
    v_release.candidate_digest
  );

  return p_release_id;
end;
$$;

create or replace function public.rollback_janani_clinical_safety_release(
  p_active_release_id uuid,
  p_replacement_release_id uuid,
  p_reason text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_active public.clinical_safety_releases%rowtype;
  v_replacement public.clinical_safety_releases%rowtype;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if p_reason is null or length(trim(p_reason)) < 3 then
    raise exception 'Rollback reason is required' using errcode = '22023';
  end if;

  select * into v_active
  from public.clinical_safety_releases release
  where release.id = p_active_release_id
  for update;

  select * into v_replacement
  from public.clinical_safety_releases release
  where release.id = p_replacement_release_id
  for update;

  if v_active.id is null or v_active.status <> 'active' then
    raise exception 'Active release not found' using errcode = '42501';
  end if;
  if v_replacement.id is null
    or v_replacement.rule_id <> v_active.rule_id
    or v_replacement.status not in ('approved', 'retired')
    or v_replacement.expires_at <= now()
  then
    raise exception 'Valid prior replacement release not found' using errcode = '42501';
  end if;

  update public.clinical_safety_releases
  set status = 'rolled_back', terminal_reason = p_reason
  where id = p_active_release_id;

  update public.clinical_safety_releases
  set status = 'active', terminal_reason = null
  where id = p_replacement_release_id;

  insert into public.clinical_safety_governance_events (
    event_type,
    aggregate_type,
    aggregate_id,
    occurred_at,
    reason,
    prior_status,
    new_status,
    content_digest,
    metadata
  ) values (
    'release_rolled_back',
    'release',
    p_active_release_id,
    now(),
    p_reason,
    'active',
    'rolled_back',
    v_active.candidate_digest,
    jsonb_build_object('replacement_release_id', p_replacement_release_id)
  );

  return p_replacement_release_id;
end;
$$;

revoke all on function public.record_janani_clinical_rule_review(
  uuid, uuid, uuid, text, text, timestamptz
) from public, anon, authenticated;
revoke all on function public.approve_janani_clinical_safety_release(
  uuid, uuid, timestamptz, timestamptz, uuid
) from public, anon, authenticated;
revoke all on function public.activate_janani_clinical_safety_release(uuid, text)
from public, anon, authenticated;
revoke all on function public.rollback_janani_clinical_safety_release(uuid, uuid, text)
from public, anon, authenticated;

grant execute on function public.record_janani_clinical_rule_review(
  uuid, uuid, uuid, text, text, timestamptz
) to service_role;
grant execute on function public.approve_janani_clinical_safety_release(
  uuid, uuid, timestamptz, timestamptz, uuid
) to service_role;
grant execute on function public.activate_janani_clinical_safety_release(uuid, text)
to service_role;
grant execute on function public.rollback_janani_clinical_safety_release(uuid, uuid, text)
to service_role;

comment on table public.clinical_safety_rule_reviews is
  'Append-only reviews bound to an exact safety-rule candidate digest.';
comment on table public.clinical_safety_governance_events is
  'Immutable clinical safety review, activation, retirement, and rollback history.';
comment on function public.approve_janani_clinical_safety_release is
  'Service-role-only release approval requiring distinct obstetrician and clinical-safety reviews.';
