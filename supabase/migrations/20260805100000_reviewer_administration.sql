-- Controlled clinical-reviewer onboarding, reverification, and deactivation.
-- End-user roles remain denied. Only trusted backend service-role RPCs may mutate reviewers.

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
      'reviewer_deactivated'
    )
  );

alter table public.clinical_safety_governance_events
  drop constraint if exists clinical_safety_governance_events_aggregate_type_check;
alter table public.clinical_safety_governance_events
  add constraint clinical_safety_governance_events_aggregate_type_check
  check (aggregate_type in ('candidate', 'release', 'ruleset', 'reviewer'));

alter table public.clinical_safety_governance_events
  add column if not exists actor_user_id uuid references auth.users(id) on delete restrict;

alter table public.clinical_safety_reviewers
  add column if not exists conflict_of_interest_attested_at timestamptz,
  add column if not exists attestation_version text,
  add column if not exists evidence_reference text,
  add column if not exists onboarded_by_user_id uuid references auth.users(id) on delete restrict,
  add column if not exists deactivated_at timestamptz,
  add column if not exists deactivated_by_user_id uuid references auth.users(id) on delete restrict,
  add column if not exists deactivation_reason text;

alter table public.clinical_safety_reviewers
  add constraint clinical_safety_reviewer_attestation_version_check
  check (attestation_version is null or length(trim(attestation_version)) >= 3);
alter table public.clinical_safety_reviewers
  add constraint clinical_safety_reviewer_evidence_reference_check
  check (evidence_reference is null or length(trim(evidence_reference)) >= 3);
alter table public.clinical_safety_reviewers
  add constraint clinical_safety_reviewer_deactivation_consistency
  check (
    (active and deactivated_at is null and deactivated_by_user_id is null and deactivation_reason is null)
    or
    (
      not active
      and deactivated_at is not null
      and deactivated_by_user_id is not null
      and length(trim(deactivation_reason)) >= 20
    )
  );

create or replace function public.guard_janani_reviewer_administration_update()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.id is distinct from old.id
    or new.user_id is distinct from old.user_id
    or new.display_name is distinct from old.display_name
    or new.role is distinct from old.role
    or new.license_jurisdiction is distinct from old.license_jurisdiction
    or new.license_reference is distinct from old.license_reference
    or new.created_at is distinct from old.created_at
  then
    raise exception 'Reviewer identity is immutable; onboard a new reviewer identity'
      using errcode = '42501';
  end if;

  if (
    new.credential_verified_at is distinct from old.credential_verified_at
    or new.credential_expires_at is distinct from old.credential_expires_at
    or new.active is distinct from old.active
    or new.conflict_of_interest_attested_at is distinct from old.conflict_of_interest_attested_at
    or new.attestation_version is distinct from old.attestation_version
    or new.evidence_reference is distinct from old.evidence_reference
    or new.onboarded_by_user_id is distinct from old.onboarded_by_user_id
    or new.deactivated_at is distinct from old.deactivated_at
    or new.deactivated_by_user_id is distinct from old.deactivated_by_user_id
    or new.deactivation_reason is distinct from old.deactivation_reason
  ) and coalesce(current_setting('janani.reviewer_admin_update', true), '') <> 'allowed'
  then
    raise exception 'Reviewer administration fields require a controlled RPC'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

create trigger guard_clinical_safety_reviewer_administration_update
before update on public.clinical_safety_reviewers
for each row execute function public.guard_janani_reviewer_administration_update();

create or replace function public.onboard_janani_clinical_reviewer(
  p_actor_user_id uuid,
  p_reviewer_user_id uuid,
  p_display_name text,
  p_role text,
  p_license_jurisdiction text,
  p_license_reference text,
  p_credential_verified_at timestamptz,
  p_credential_expires_at timestamptz,
  p_conflict_of_interest_attested_at timestamptz,
  p_attestation_version text,
  p_evidence_reference text,
  p_reason text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_reviewer_id uuid := gen_random_uuid();
  v_now timestamptz := now();
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if not exists (select 1 from auth.users where id = p_actor_user_id) then
    raise exception 'Governance administrator identity not found' using errcode = 'P0002';
  end if;
  if p_reviewer_user_id is not null
    and not exists (select 1 from auth.users where id = p_reviewer_user_id)
  then
    raise exception 'Reviewer user identity not found' using errcode = 'P0002';
  end if;
  if p_role not in ('obstetrician', 'clinical_safety', 'language_reviewer') then
    raise exception 'Unsupported reviewer role' using errcode = '22023';
  end if;
  if length(trim(p_display_name)) < 2
    or length(trim(p_license_jurisdiction)) < 2
    or length(trim(p_license_reference)) < 3
  then
    raise exception 'Reviewer identity fields are invalid' using errcode = '22023';
  end if;
  if p_credential_verified_at > v_now
    or p_credential_expires_at <= v_now
    or p_credential_expires_at <= p_credential_verified_at
  then
    raise exception 'Reviewer credential window is invalid' using errcode = '22023';
  end if;
  if p_conflict_of_interest_attested_at > p_credential_verified_at then
    raise exception 'Conflict-of-interest attestation must precede credential verification'
      using errcode = '22023';
  end if;
  if length(trim(p_attestation_version)) < 3
    or length(trim(p_evidence_reference)) < 3
    or length(trim(p_reason)) < 20
  then
    raise exception 'Reviewer onboarding evidence or reason is incomplete'
      using errcode = '22023';
  end if;

  insert into public.clinical_safety_reviewers (
    id,
    user_id,
    display_name,
    role,
    license_jurisdiction,
    license_reference,
    credential_verified_at,
    credential_expires_at,
    active,
    conflict_of_interest_attested_at,
    attestation_version,
    evidence_reference,
    onboarded_by_user_id
  ) values (
    v_reviewer_id,
    p_reviewer_user_id,
    trim(p_display_name),
    p_role,
    trim(p_license_jurisdiction),
    trim(p_license_reference),
    p_credential_verified_at,
    p_credential_expires_at,
    true,
    p_conflict_of_interest_attested_at,
    trim(p_attestation_version),
    trim(p_evidence_reference),
    p_actor_user_id
  );

  insert into public.clinical_safety_governance_events (
    event_type,
    aggregate_type,
    aggregate_id,
    actor_user_id,
    occurred_at,
    reason,
    prior_status,
    new_status,
    metadata
  ) values (
    'reviewer_onboarded',
    'reviewer',
    v_reviewer_id,
    p_actor_user_id,
    v_now,
    trim(p_reason),
    null,
    'active',
    jsonb_build_object(
      'reviewer_role', p_role,
      'attestation_version', trim(p_attestation_version),
      'credential_expires_at', p_credential_expires_at
    )
  );

  return v_reviewer_id;
end;
$$;

create or replace function public.reverify_janani_clinical_reviewer(
  p_actor_user_id uuid,
  p_reviewer_id uuid,
  p_credential_verified_at timestamptz,
  p_credential_expires_at timestamptz,
  p_conflict_of_interest_attested_at timestamptz,
  p_attestation_version text,
  p_evidence_reference text,
  p_reason text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_now timestamptz := now();
  v_reviewer public.clinical_safety_reviewers%rowtype;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if not exists (select 1 from auth.users where id = p_actor_user_id) then
    raise exception 'Governance administrator identity not found' using errcode = 'P0002';
  end if;

  select * into v_reviewer
  from public.clinical_safety_reviewers
  where id = p_reviewer_id
  for update;

  if v_reviewer.id is null then
    raise exception 'Clinical reviewer not found' using errcode = 'P0002';
  end if;
  if not v_reviewer.active then
    raise exception 'Inactive reviewers cannot be reverified' using errcode = '42501';
  end if;
  if p_credential_verified_at > v_now
    or p_credential_expires_at <= v_now
    or p_credential_expires_at <= p_credential_verified_at
  then
    raise exception 'Reviewer credential window is invalid' using errcode = '22023';
  end if;
  if p_conflict_of_interest_attested_at > p_credential_verified_at then
    raise exception 'Conflict-of-interest attestation must precede credential verification'
      using errcode = '22023';
  end if;
  if length(trim(p_attestation_version)) < 3
    or length(trim(p_evidence_reference)) < 3
    or length(trim(p_reason)) < 20
  then
    raise exception 'Reviewer reverification evidence or reason is incomplete'
      using errcode = '22023';
  end if;

  perform set_config('janani.reviewer_admin_update', 'allowed', true);
  update public.clinical_safety_reviewers
  set
    credential_verified_at = p_credential_verified_at,
    credential_expires_at = p_credential_expires_at,
    conflict_of_interest_attested_at = p_conflict_of_interest_attested_at,
    attestation_version = trim(p_attestation_version),
    evidence_reference = trim(p_evidence_reference)
  where id = p_reviewer_id;

  insert into public.clinical_safety_governance_events (
    event_type,
    aggregate_type,
    aggregate_id,
    actor_user_id,
    occurred_at,
    reason,
    prior_status,
    new_status,
    metadata
  ) values (
    'reviewer_reverified',
    'reviewer',
    p_reviewer_id,
    p_actor_user_id,
    v_now,
    trim(p_reason),
    'active',
    'active',
    jsonb_build_object(
      'attestation_version', trim(p_attestation_version),
      'prior_credential_expires_at', v_reviewer.credential_expires_at,
      'credential_expires_at', p_credential_expires_at
    )
  );

  return p_reviewer_id;
end;
$$;

create or replace function public.deactivate_janani_clinical_reviewer(
  p_actor_user_id uuid,
  p_reviewer_id uuid,
  p_reason text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_now timestamptz := now();
  v_reviewer public.clinical_safety_reviewers%rowtype;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if not exists (select 1 from auth.users where id = p_actor_user_id) then
    raise exception 'Governance administrator identity not found' using errcode = 'P0002';
  end if;
  if length(trim(p_reason)) < 20 then
    raise exception 'Reviewer deactivation reason is incomplete' using errcode = '22023';
  end if;

  select * into v_reviewer
  from public.clinical_safety_reviewers
  where id = p_reviewer_id
  for update;

  if v_reviewer.id is null then
    raise exception 'Clinical reviewer not found' using errcode = 'P0002';
  end if;
  if not v_reviewer.active then
    raise exception 'Clinical reviewer is already inactive' using errcode = '42501';
  end if;
  if exists (
    select 1
    from public.clinical_safety_release_approvals approval
    join public.clinical_safety_releases release on release.id = approval.release_id
    where approval.reviewer_id = p_reviewer_id
      and release.status = 'active'
  ) then
    raise exception 'Reviewer has approvals on an active release; rollback or retire it first'
      using errcode = '42501';
  end if;

  perform set_config('janani.reviewer_admin_update', 'allowed', true);
  update public.clinical_safety_reviewers
  set
    active = false,
    deactivated_at = v_now,
    deactivated_by_user_id = p_actor_user_id,
    deactivation_reason = trim(p_reason)
  where id = p_reviewer_id;

  insert into public.clinical_safety_governance_events (
    event_type,
    aggregate_type,
    aggregate_id,
    actor_user_id,
    occurred_at,
    reason,
    prior_status,
    new_status,
    metadata
  ) values (
    'reviewer_deactivated',
    'reviewer',
    p_reviewer_id,
    p_actor_user_id,
    v_now,
    trim(p_reason),
    'active',
    'inactive',
    jsonb_build_object('reviewer_role', v_reviewer.role)
  );

  return p_reviewer_id;
end;
$$;

revoke all on function public.onboard_janani_clinical_reviewer(
  uuid, uuid, text, text, text, text, timestamptz, timestamptz,
  timestamptz, text, text, text
) from public, anon, authenticated;
revoke all on function public.reverify_janani_clinical_reviewer(
  uuid, uuid, timestamptz, timestamptz, timestamptz, text, text, text
) from public, anon, authenticated;
revoke all on function public.deactivate_janani_clinical_reviewer(uuid, uuid, text)
from public, anon, authenticated;

grant execute on function public.onboard_janani_clinical_reviewer(
  uuid, uuid, text, text, text, text, timestamptz, timestamptz,
  timestamptz, text, text, text
) to service_role;
grant execute on function public.reverify_janani_clinical_reviewer(
  uuid, uuid, timestamptz, timestamptz, timestamptz, text, text, text
) to service_role;
grant execute on function public.deactivate_janani_clinical_reviewer(uuid, uuid, text)
to service_role;

comment on function public.onboard_janani_clinical_reviewer is
  'Service-role-only reviewer onboarding with credential and conflict-of-interest evidence references.';
comment on function public.reverify_janani_clinical_reviewer is
  'Service-role-only reviewer credential and conflict-of-interest reverification.';
comment on function public.deactivate_janani_clinical_reviewer is
  'Service-role-only reviewer deactivation blocked while the reviewer approves an active release.';

notify pgrst, 'reload schema';
