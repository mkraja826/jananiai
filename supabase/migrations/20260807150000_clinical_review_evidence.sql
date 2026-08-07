-- Immutable synthetic pre-clinical review packets and incident-rehearsal evidence.
-- End-user roles remain denied. Only trusted backend service-role RPCs may record evidence.

alter table public.clinical_safety_governance_events
  drop constraint if exists clinical_safety_governance_events_event_type_check;
alter table public.clinical_safety_governance_events
  add constraint clinical_safety_governance_events_event_type_check
  check (
    event_type in (
      'review_recorded',
      'release_approved',
      'release_activated',
      'release_retired',
      'release_rolled_back',
      'ruleset_approved',
      'ruleset_activated',
      'ruleset_retired',
      'ruleset_rolled_back',
      'reviewer_onboarded',
      'reviewer_reverified',
      'reviewer_deactivated',
      'review_packet_recorded',
      'rehearsal_recorded'
    )
  );

alter table public.clinical_safety_governance_events
  drop constraint if exists clinical_safety_governance_events_aggregate_type_check;
alter table public.clinical_safety_governance_events
  add constraint clinical_safety_governance_events_aggregate_type_check
  check (
    aggregate_type in (
      'candidate', 'release', 'ruleset', 'reviewer', 'review_packet', 'rehearsal'
    )
  );

create table if not exists public.clinical_safety_review_packets (
  id uuid primary key,
  candidate_id uuid not null references public.clinical_safety_rule_candidates(id) on delete restrict,
  rule_id text not null check (length(trim(rule_id)) >= 3),
  packet_version text not null check (length(trim(packet_version)) >= 1),
  packet_digest text not null unique check (packet_digest ~ '^[0-9a-f]{64}$'),
  candidate_digest text not null check (candidate_digest ~ '^[0-9a-f]{64}$'),
  dataset_version text not null check (length(trim(dataset_version)) >= 1),
  dataset_digest text not null check (dataset_digest ~ '^[0-9a-f]{64}$'),
  total_cases integer not null check (total_cases > 0),
  passed_cases integer not null check (passed_cases = total_cases),
  required_categories text[] not null check (cardinality(required_categories) = 9),
  placeholder_sources_present boolean not null,
  synthetic_only boolean not null default true check (synthetic_only),
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  generated_at timestamptz not null,
  recorded_at timestamptz not null default now(),
  recorded_by_user_id uuid not null references auth.users(id) on delete restrict
);

create table if not exists public.clinical_safety_rehearsals (
  id uuid primary key,
  scenario text not null check (scenario = 'emergency_ruleset_rollback'),
  active_ruleset_before uuid not null references public.clinical_safety_rulesets(id) on delete restrict,
  restored_ruleset_after uuid not null references public.clinical_safety_rulesets(id) on delete restrict,
  rolled_back_ruleset uuid not null references public.clinical_safety_rulesets(id) on delete restrict,
  started_at timestamptz not null,
  completed_at timestamptz not null,
  passed boolean not null,
  reason text not null check (length(trim(reason)) >= 10),
  steps jsonb not null check (jsonb_typeof(steps) = 'array'),
  synthetic_only boolean not null default true check (synthetic_only),
  recorded_at timestamptz not null default now(),
  recorded_by_user_id uuid not null references auth.users(id) on delete restrict,
  constraint clinical_safety_rehearsal_time_order check (completed_at >= started_at),
  constraint clinical_safety_rehearsal_ruleset_identity check (
    active_ruleset_before <> restored_ruleset_after
    and rolled_back_ruleset = active_ruleset_before
  )
);

create trigger prevent_clinical_safety_review_packet_mutation
before update or delete on public.clinical_safety_review_packets
for each row execute function public.prevent_janani_governance_history_mutation();

create trigger prevent_clinical_safety_rehearsal_mutation
before update or delete on public.clinical_safety_rehearsals
for each row execute function public.prevent_janani_governance_history_mutation();

alter table public.clinical_safety_review_packets enable row level security;
alter table public.clinical_safety_rehearsals enable row level security;

revoke all on table public.clinical_safety_review_packets from public, anon, authenticated;
revoke all on table public.clinical_safety_rehearsals from public, anon, authenticated;
grant select on table public.clinical_safety_review_packets to service_role;
grant select on table public.clinical_safety_rehearsals to service_role;

create or replace function public.record_janani_clinical_review_packet(
  p_actor_user_id uuid,
  p_payload jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_packet_id uuid;
  v_candidate_id uuid;
  v_candidate public.clinical_safety_rule_candidates%rowtype;
  v_required_categories text[];
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if not exists (select 1 from auth.users where id = p_actor_user_id) then
    raise exception 'Governance administrator identity not found' using errcode = 'P0002';
  end if;
  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception 'Review packet payload must be a JSON object' using errcode = '22023';
  end if;
  if coalesce((p_payload ->> 'synthetic_only')::boolean, false) is not true then
    raise exception 'Current review packet persistence is synthetic-only'
      using errcode = '42501';
  end if;

  v_packet_id := (p_payload ->> 'packet_id')::uuid;
  v_candidate_id := (p_payload ->> 'candidate_id')::uuid;
  select * into v_candidate
  from public.clinical_safety_rule_candidates candidate
  where candidate.id = v_candidate_id;

  if v_candidate.id is null then
    raise exception 'Clinical safety candidate not found' using errcode = 'P0002';
  end if;
  if v_candidate.rule_id <> p_payload ->> 'rule_id'
    or v_candidate.content_digest <> p_payload ->> 'candidate_digest'
  then
    raise exception 'Review packet candidate binding does not match stored content'
      using errcode = '42501';
  end if;
  if (p_payload -> 'validation' ->> 'passed_cases')::integer
      <> (p_payload -> 'validation' ->> 'total_cases')::integer
    or (p_payload -> 'validation' ->> 'total_cases')::integer <= 0
  then
    raise exception 'Review packet requires fully passing validation evidence'
      using errcode = '42501';
  end if;

  select array_agg(value order by value)
  into v_required_categories
  from jsonb_array_elements_text(p_payload -> 'validation' -> 'categories') value;

  if cardinality(v_required_categories) <> 9
    or cardinality(v_required_categories) <> (
      select count(distinct value)
      from unnest(v_required_categories) value
    )
    or not v_required_categories @> array[
      'true_positive', 'true_negative', 'boundary', 'interaction', 'regression',
      'ambiguity', 'missing_data', 'adversarial', 'cross_rule'
    ]::text[]
  then
    raise exception 'Review packet validation categories are incomplete'
      using errcode = '42501';
  end if;

  insert into public.clinical_safety_review_packets (
    id,
    candidate_id,
    rule_id,
    packet_version,
    packet_digest,
    candidate_digest,
    dataset_version,
    dataset_digest,
    total_cases,
    passed_cases,
    required_categories,
    placeholder_sources_present,
    synthetic_only,
    payload,
    generated_at,
    recorded_by_user_id
  ) values (
    v_packet_id,
    v_candidate_id,
    p_payload ->> 'rule_id',
    p_payload ->> 'packet_version',
    p_payload ->> 'packet_digest',
    p_payload ->> 'candidate_digest',
    p_payload -> 'validation' ->> 'dataset_version',
    p_payload -> 'validation' ->> 'dataset_digest',
    (p_payload -> 'validation' ->> 'total_cases')::integer,
    (p_payload -> 'validation' ->> 'passed_cases')::integer,
    v_required_categories,
    (p_payload ->> 'placeholder_sources_present')::boolean,
    true,
    p_payload,
    (p_payload ->> 'generated_at')::timestamptz,
    p_actor_user_id
  );

  insert into public.clinical_safety_governance_events (
    event_type,
    aggregate_type,
    aggregate_id,
    actor_user_id,
    occurred_at,
    reason,
    content_digest,
    metadata
  ) values (
    'review_packet_recorded',
    'review_packet',
    v_packet_id,
    p_actor_user_id,
    now(),
    'Synthetic pre-clinical review packet recorded',
    p_payload ->> 'packet_digest',
    jsonb_build_object(
      'candidate_id', v_candidate_id,
      'rule_id', p_payload ->> 'rule_id',
      'dataset_version', p_payload -> 'validation' ->> 'dataset_version'
    )
  );

  return v_packet_id;
end;
$$;

create or replace function public.record_janani_safety_rehearsal(
  p_actor_user_id uuid,
  p_payload jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_rehearsal_id uuid;
  v_active_ruleset uuid;
  v_restored_ruleset uuid;
  v_rolled_back_ruleset uuid;
  v_step_names text[];
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if not exists (select 1 from auth.users where id = p_actor_user_id) then
    raise exception 'Governance administrator identity not found' using errcode = 'P0002';
  end if;
  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception 'Rehearsal payload must be a JSON object' using errcode = '22023';
  end if;
  if coalesce((p_payload ->> 'synthetic_only')::boolean, false) is not true then
    raise exception 'Current rehearsal persistence is synthetic-only'
      using errcode = '42501';
  end if;
  if p_payload ->> 'scenario' <> 'emergency_ruleset_rollback' then
    raise exception 'Unsupported safety rehearsal scenario' using errcode = '22023';
  end if;

  v_rehearsal_id := (p_payload ->> 'rehearsal_id')::uuid;
  v_active_ruleset := (p_payload ->> 'active_ruleset_before')::uuid;
  v_restored_ruleset := (p_payload ->> 'restored_ruleset_after')::uuid;
  v_rolled_back_ruleset := (p_payload ->> 'rolled_back_ruleset')::uuid;

  if v_active_ruleset = v_restored_ruleset or v_rolled_back_ruleset <> v_active_ruleset then
    raise exception 'Rehearsal ruleset identities are inconsistent' using errcode = '42501';
  end if;
  if not exists (
    select 1 from public.clinical_safety_rulesets ruleset
    where ruleset.id = v_restored_ruleset and ruleset.status = 'active'
  ) then
    raise exception 'Restored rehearsal ruleset is not active' using errcode = '42501';
  end if;
  if not exists (
    select 1 from public.clinical_safety_rulesets ruleset
    where ruleset.id = v_rolled_back_ruleset and ruleset.status = 'rolled_back'
  ) then
    raise exception 'Incident ruleset is not in rolled-back state' using errcode = '42501';
  end if;

  select array_agg(value order by value)
  into v_step_names
  from jsonb_array_elements(p_payload -> 'steps') step,
       lateral (select step ->> 'name' as value) names;

  if cardinality(v_step_names) <> 6
    or cardinality(v_step_names) <> (
      select count(distinct value) from unnest(v_step_names) value
    )
    or not v_step_names @> array[
      'detect_incident',
      'verify_active_manifest',
      'execute_atomic_rollback',
      'verify_restored_manifest',
      'verify_rolled_back_state',
      'record_audit_evidence'
    ]::text[]
  then
    raise exception 'Rehearsal steps are incomplete' using errcode = '42501';
  end if;

  insert into public.clinical_safety_rehearsals (
    id,
    scenario,
    active_ruleset_before,
    restored_ruleset_after,
    rolled_back_ruleset,
    started_at,
    completed_at,
    passed,
    reason,
    steps,
    synthetic_only,
    recorded_by_user_id
  ) values (
    v_rehearsal_id,
    p_payload ->> 'scenario',
    v_active_ruleset,
    v_restored_ruleset,
    v_rolled_back_ruleset,
    (p_payload ->> 'started_at')::timestamptz,
    (p_payload ->> 'completed_at')::timestamptz,
    (p_payload ->> 'passed')::boolean,
    trim(p_payload ->> 'reason'),
    p_payload -> 'steps',
    true,
    p_actor_user_id
  );

  insert into public.clinical_safety_governance_events (
    event_type,
    aggregate_type,
    aggregate_id,
    actor_user_id,
    occurred_at,
    reason,
    metadata
  ) values (
    'rehearsal_recorded',
    'rehearsal',
    v_rehearsal_id,
    p_actor_user_id,
    now(),
    trim(p_payload ->> 'reason'),
    jsonb_build_object(
      'scenario', p_payload ->> 'scenario',
      'passed', (p_payload ->> 'passed')::boolean,
      'active_ruleset_before', v_active_ruleset,
      'restored_ruleset_after', v_restored_ruleset
    )
  );

  return v_rehearsal_id;
end;
$$;

revoke all on function public.record_janani_clinical_review_packet(uuid, jsonb)
from public, anon, authenticated;
revoke all on function public.record_janani_safety_rehearsal(uuid, jsonb)
from public, anon, authenticated;
grant execute on function public.record_janani_clinical_review_packet(uuid, jsonb)
to service_role;
grant execute on function public.record_janani_safety_rehearsal(uuid, jsonb)
to service_role;

notify pgrst, 'reload schema';
