-- Atomic clinical-safety ruleset activation and rollback.
-- Individual rule releases remain review units; a complete ruleset is the deployable unit.

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
      'ruleset_rolled_back'
    )
  );

alter table public.clinical_safety_governance_events
  drop constraint if exists clinical_safety_governance_events_aggregate_type_check;
alter table public.clinical_safety_governance_events
  add constraint clinical_safety_governance_events_aggregate_type_check
  check (aggregate_type in ('candidate', 'release', 'ruleset'));

create table if not exists public.clinical_safety_rulesets (
  id uuid primary key default gen_random_uuid(),
  version text not null check (length(trim(version)) >= 1),
  status text not null default 'approved'
    check (status in ('approved', 'active', 'expired', 'retired', 'rolled_back')),
  required_rule_ids text[] not null check (cardinality(required_rule_ids) > 0),
  manifest_digest text not null unique check (manifest_digest ~ '^[0-9a-f]{64}$'),
  approved_at timestamptz not null,
  activates_at timestamptz not null,
  expires_at timestamptz not null,
  supersedes_ruleset_id uuid references public.clinical_safety_rulesets(id) on delete restrict,
  terminal_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint clinical_safety_ruleset_activation_window
    check (activates_at >= approved_at and expires_at > activates_at),
  unique (version)
);

create table if not exists public.clinical_safety_ruleset_members (
  ruleset_id uuid not null references public.clinical_safety_rulesets(id) on delete restrict,
  release_id uuid not null references public.clinical_safety_releases(id) on delete restrict,
  rule_id text not null check (length(trim(rule_id)) >= 3),
  candidate_digest text not null check (candidate_digest ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  primary key (ruleset_id, rule_id),
  unique (ruleset_id, release_id)
);

create unique index if not exists one_active_clinical_safety_ruleset
on public.clinical_safety_rulesets ((status))
where status = 'active';

create trigger set_clinical_safety_rulesets_updated_at
before update on public.clinical_safety_rulesets
for each row execute function public.set_janani_governance_updated_at();

create or replace function public.prevent_janani_ruleset_content_mutation()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.id is distinct from old.id
    or new.version is distinct from old.version
    or new.required_rule_ids is distinct from old.required_rule_ids
    or new.manifest_digest is distinct from old.manifest_digest
    or new.approved_at is distinct from old.approved_at
    or new.activates_at is distinct from old.activates_at
    or new.expires_at is distinct from old.expires_at
    or new.supersedes_ruleset_id is distinct from old.supersedes_ruleset_id
    or new.created_at is distinct from old.created_at
  then
    raise exception 'Clinical safety ruleset content is immutable; create a new version'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger prevent_clinical_safety_ruleset_content_mutation
before update on public.clinical_safety_rulesets
for each row execute function public.prevent_janani_ruleset_content_mutation();

create trigger prevent_clinical_safety_ruleset_member_mutation
before update or delete on public.clinical_safety_ruleset_members
for each row execute function public.prevent_janani_governance_history_mutation();

alter table public.clinical_safety_rulesets enable row level security;
alter table public.clinical_safety_ruleset_members enable row level security;

revoke all on table public.clinical_safety_rulesets from public, anon, authenticated;
revoke all on table public.clinical_safety_ruleset_members from public, anon, authenticated;

grant select, insert, update on table public.clinical_safety_rulesets to service_role;
grant select, insert on table public.clinical_safety_ruleset_members to service_role;

create or replace function public.approve_janani_clinical_safety_ruleset(
  p_ruleset_id uuid,
  p_version text,
  p_required_rule_ids text[],
  p_release_ids uuid[],
  p_activates_at timestamptz,
  p_expires_at timestamptz,
  p_supersedes_ruleset_id uuid default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_now timestamptz := now();
  v_required_rule_ids text[];
  v_release_rule_ids text[];
  v_release_count integer;
  v_manifest_digest text;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if p_version is null or length(trim(p_version)) < 1 then
    raise exception 'Ruleset version is required' using errcode = '22023';
  end if;
  if p_required_rule_ids is null or cardinality(p_required_rule_ids) < 1 then
    raise exception 'At least one required rule ID is required' using errcode = '22023';
  end if;
  if p_release_ids is null or cardinality(p_release_ids) < 1 then
    raise exception 'At least one release ID is required' using errcode = '22023';
  end if;
  if p_activates_at < v_now or p_expires_at <= p_activates_at then
    raise exception 'Invalid ruleset activation window' using errcode = '22023';
  end if;
  if exists (
    select 1 from unnest(p_required_rule_ids) rule_id
    where rule_id is null or length(trim(rule_id)) < 3
  ) then
    raise exception 'Required rule IDs must be valid' using errcode = '22023';
  end if;
  if cardinality(p_required_rule_ids) <> (
    select count(distinct rule_id) from unnest(p_required_rule_ids) rule_id
  ) then
    raise exception 'Required rule IDs must be unique' using errcode = '22023';
  end if;
  if cardinality(p_release_ids) <> (
    select count(distinct release_id) from unnest(p_release_ids) release_id
  ) then
    raise exception 'Release IDs must be unique' using errcode = '22023';
  end if;

  select array_agg(rule_id order by rule_id)
  into v_required_rule_ids
  from unnest(p_required_rule_ids) rule_id;

  perform 1
  from public.clinical_safety_releases release
  where release.id = any(p_release_ids)
  order by release.id
  for update;

  select count(*), array_agg(release.rule_id order by release.rule_id)
  into v_release_count, v_release_rule_ids
  from public.clinical_safety_releases release
  where release.id = any(p_release_ids);

  if v_release_count <> cardinality(p_release_ids) then
    raise exception 'Every ruleset release must exist' using errcode = 'P0002';
  end if;
  if v_release_rule_ids is distinct from v_required_rule_ids then
    raise exception 'Ruleset releases must exactly match required rule IDs'
      using errcode = '42501';
  end if;
  if exists (
    select 1 from public.clinical_safety_releases release
    where release.id = any(p_release_ids)
      and release.status <> 'approved'
  ) then
    raise exception 'Every ruleset member must be an approved release'
      using errcode = '42501';
  end if;
  if exists (
    select 1 from public.clinical_safety_releases release
    where release.id = any(p_release_ids)
      and (
        release.activates_at > p_activates_at
        or release.expires_at < p_expires_at
      )
  ) then
    raise exception 'A member release does not cover the ruleset activation window'
      using errcode = '42501';
  end if;
  if p_supersedes_ruleset_id is not null and not exists (
    select 1 from public.clinical_safety_rulesets ruleset
    where ruleset.id = p_supersedes_ruleset_id
  ) then
    raise exception 'Superseded ruleset not found' using errcode = 'P0002';
  end if;

  select encode(
    digest(
      p_version || '|' || array_to_string(v_required_rule_ids, ',') || '|' ||
      string_agg(
        release.rule_id || ':' || release.id::text || ':' || release.candidate_digest,
        '|' order by release.rule_id
      ),
      'sha256'
    ),
    'hex'
  )
  into v_manifest_digest
  from public.clinical_safety_releases release
  where release.id = any(p_release_ids);

  insert into public.clinical_safety_rulesets (
    id,
    version,
    status,
    required_rule_ids,
    manifest_digest,
    approved_at,
    activates_at,
    expires_at,
    supersedes_ruleset_id
  ) values (
    p_ruleset_id,
    p_version,
    'approved',
    v_required_rule_ids,
    v_manifest_digest,
    v_now,
    p_activates_at,
    p_expires_at,
    p_supersedes_ruleset_id
  );

  insert into public.clinical_safety_ruleset_members (
    ruleset_id,
    release_id,
    rule_id,
    candidate_digest
  )
  select
    p_ruleset_id,
    release.id,
    release.rule_id,
    release.candidate_digest
  from public.clinical_safety_releases release
  where release.id = any(p_release_ids)
  order by release.rule_id;

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
    'ruleset_approved',
    'ruleset',
    p_ruleset_id,
    v_now,
    'Complete clinical safety ruleset approved for activation',
    null,
    'approved',
    v_manifest_digest,
    jsonb_build_object(
      'version', p_version,
      'required_rule_ids', to_jsonb(v_required_rule_ids),
      'release_count', v_release_count
    )
  );

  return p_ruleset_id;
end;
$$;

create or replace function public.activate_janani_clinical_safety_ruleset(
  p_ruleset_id uuid,
  p_reason text default 'Approved clinical safety ruleset activated'
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_now timestamptz := now();
  v_ruleset public.clinical_safety_rulesets%rowtype;
  v_current public.clinical_safety_rulesets%rowtype;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if p_reason is null or length(trim(p_reason)) < 3 then
    raise exception 'Activation reason is required' using errcode = '22023';
  end if;

  select * into v_ruleset
  from public.clinical_safety_rulesets ruleset
  where ruleset.id = p_ruleset_id
  for update;

  if v_ruleset.id is null then
    raise exception 'Clinical safety ruleset not found' using errcode = 'P0002';
  end if;
  if v_ruleset.status <> 'approved' then
    raise exception 'Only approved rulesets may be activated' using errcode = '42501';
  end if;
  if v_now < v_ruleset.activates_at or v_now >= v_ruleset.expires_at then
    raise exception 'Ruleset is outside its activation window' using errcode = '42501';
  end if;
  if cardinality(v_ruleset.required_rule_ids) <> (
    select count(*) from public.clinical_safety_ruleset_members member
    where member.ruleset_id = p_ruleset_id
  ) then
    raise exception 'Ruleset manifest is incomplete' using errcode = '42501';
  end if;
  if exists (
    select 1
    from unnest(v_ruleset.required_rule_ids) required_rule_id
    where not exists (
      select 1 from public.clinical_safety_ruleset_members member
      where member.ruleset_id = p_ruleset_id
        and member.rule_id = required_rule_id
    )
  ) then
    raise exception 'Ruleset manifest does not match required rule IDs'
      using errcode = '42501';
  end if;

  perform 1
  from public.clinical_safety_releases release
  where release.id in (
    select member.release_id
    from public.clinical_safety_ruleset_members member
    where member.ruleset_id = p_ruleset_id
  ) or release.status = 'active'
  order by release.id
  for update;

  if exists (
    select 1
    from public.clinical_safety_ruleset_members member
    left join public.clinical_safety_releases release on release.id = member.release_id
    where member.ruleset_id = p_ruleset_id
      and (
        release.id is null
        or release.rule_id <> member.rule_id
        or release.candidate_digest <> member.candidate_digest
        or release.status not in ('approved', 'active')
        or release.activates_at > v_now
        or release.expires_at <= v_now
      )
  ) then
    raise exception 'Ruleset contains an invalid or expired member release'
      using errcode = '42501';
  end if;

  select * into v_current
  from public.clinical_safety_rulesets ruleset
  where ruleset.status = 'active' and ruleset.id <> p_ruleset_id
  for update;

  if v_current.id is null then
    if exists (select 1 from public.clinical_safety_releases where status = 'active') then
      raise exception 'Active release drift detected without an active ruleset'
        using errcode = '42501';
    end if;
  else
    if exists (
      select 1 from public.clinical_safety_releases release
      where release.status = 'active'
        and not exists (
          select 1 from public.clinical_safety_ruleset_members member
          where member.ruleset_id = v_current.id
            and member.release_id = release.id
        )
    ) or exists (
      select 1 from public.clinical_safety_ruleset_members member
      left join public.clinical_safety_releases release on release.id = member.release_id
      where member.ruleset_id = v_current.id
        and (release.id is null or release.status <> 'active')
    ) then
      raise exception 'Current active ruleset and active releases have drifted'
        using errcode = '42501';
    end if;
  end if;

  if v_current.id is not null then
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
      'ruleset_retired',
      'ruleset',
      v_current.id,
      v_now,
      p_reason,
      'active',
      'retired',
      v_current.manifest_digest,
      jsonb_build_object('replacement_ruleset_id', p_ruleset_id)
    );

    update public.clinical_safety_rulesets
    set status = 'retired', terminal_reason = p_reason
    where id = v_current.id;
  end if;

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
  )
  select
    'release_retired',
    'release',
    release.id,
    v_now,
    p_reason,
    'active',
    'retired',
    release.candidate_digest,
    jsonb_build_object('replacement_ruleset_id', p_ruleset_id)
  from public.clinical_safety_releases release
  where release.status = 'active'
    and not exists (
      select 1 from public.clinical_safety_ruleset_members member
      where member.ruleset_id = p_ruleset_id
        and member.release_id = release.id
    );

  update public.clinical_safety_releases release
  set status = 'retired', terminal_reason = p_reason
  where release.status = 'active'
    and not exists (
      select 1 from public.clinical_safety_ruleset_members member
      where member.ruleset_id = p_ruleset_id
        and member.release_id = release.id
    );

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
  )
  select
    'release_activated',
    'release',
    release.id,
    v_now,
    p_reason,
    release.status,
    'active',
    release.candidate_digest,
    jsonb_build_object('ruleset_id', p_ruleset_id)
  from public.clinical_safety_ruleset_members member
  join public.clinical_safety_releases release on release.id = member.release_id
  where member.ruleset_id = p_ruleset_id
    and release.status <> 'active';

  update public.clinical_safety_releases release
  set status = 'active', terminal_reason = null
  where release.id in (
    select member.release_id
    from public.clinical_safety_ruleset_members member
    where member.ruleset_id = p_ruleset_id
  );

  update public.clinical_safety_rulesets
  set status = 'active', terminal_reason = null
  where id = p_ruleset_id;

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
    'ruleset_activated',
    'ruleset',
    p_ruleset_id,
    v_now,
    p_reason,
    v_ruleset.status,
    'active',
    v_ruleset.manifest_digest,
    jsonb_build_object('replaced_ruleset_id', v_current.id)
  );

  if exists (
    select 1 from public.clinical_safety_releases release
    where release.status = 'active'
      and not exists (
        select 1 from public.clinical_safety_ruleset_members member
        where member.ruleset_id = p_ruleset_id
          and member.release_id = release.id
      )
  ) or exists (
    select 1 from public.clinical_safety_ruleset_members member
    left join public.clinical_safety_releases release on release.id = member.release_id
    where member.ruleset_id = p_ruleset_id
      and (release.id is null or release.status <> 'active')
  ) then
    raise exception 'Atomic ruleset activation failed final consistency check'
      using errcode = '42501';
  end if;

  return p_ruleset_id;
end;
$$;

create or replace function public.rollback_janani_clinical_safety_ruleset(
  p_active_ruleset_id uuid,
  p_replacement_ruleset_id uuid,
  p_reason text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_now timestamptz := now();
  v_active public.clinical_safety_rulesets%rowtype;
  v_replacement public.clinical_safety_rulesets%rowtype;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if p_reason is null or length(trim(p_reason)) < 3 then
    raise exception 'Rollback reason is required' using errcode = '22023';
  end if;
  if p_active_ruleset_id = p_replacement_ruleset_id then
    raise exception 'Rollback requires a distinct replacement ruleset'
      using errcode = '22023';
  end if;

  select * into v_active
  from public.clinical_safety_rulesets ruleset
  where ruleset.id = p_active_ruleset_id
  for update;

  select * into v_replacement
  from public.clinical_safety_rulesets ruleset
  where ruleset.id = p_replacement_ruleset_id
  for update;

  if v_active.id is null or v_active.status <> 'active' then
    raise exception 'Active ruleset not found' using errcode = '42501';
  end if;
  if v_replacement.id is null
    or v_replacement.status not in ('approved', 'retired')
    or v_now < v_replacement.activates_at
    or v_now >= v_replacement.expires_at
  then
    raise exception 'Valid prior replacement ruleset not found' using errcode = '42501';
  end if;
  if cardinality(v_replacement.required_rule_ids) <> (
    select count(*) from public.clinical_safety_ruleset_members member
    where member.ruleset_id = p_replacement_ruleset_id
  ) then
    raise exception 'Replacement ruleset manifest is incomplete' using errcode = '42501';
  end if;

  perform 1
  from public.clinical_safety_releases release
  where release.status = 'active'
    or release.id in (
      select member.release_id
      from public.clinical_safety_ruleset_members member
      where member.ruleset_id = p_replacement_ruleset_id
    )
  order by release.id
  for update;

  if exists (
    select 1 from public.clinical_safety_releases release
    where release.status = 'active'
      and not exists (
        select 1 from public.clinical_safety_ruleset_members member
        where member.ruleset_id = p_active_ruleset_id
          and member.release_id = release.id
      )
  ) or exists (
    select 1 from public.clinical_safety_ruleset_members member
    left join public.clinical_safety_releases release on release.id = member.release_id
    where member.ruleset_id = p_active_ruleset_id
      and (release.id is null or release.status <> 'active')
  ) then
    raise exception 'Current active ruleset and active releases have drifted'
      using errcode = '42501';
  end if;

  if exists (
    select 1
    from public.clinical_safety_ruleset_members member
    left join public.clinical_safety_releases release on release.id = member.release_id
    where member.ruleset_id = p_replacement_ruleset_id
      and (
        release.id is null
        or release.rule_id <> member.rule_id
        or release.candidate_digest <> member.candidate_digest
        or release.status not in ('approved', 'retired', 'active')
        or release.activates_at > v_now
        or release.expires_at <= v_now
      )
  ) then
    raise exception 'Replacement ruleset contains an invalid or expired member release'
      using errcode = '42501';
  end if;

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
  )
  select
    'release_rolled_back',
    'release',
    release.id,
    v_now,
    p_reason,
    'active',
    'rolled_back',
    release.candidate_digest,
    jsonb_build_object('replacement_ruleset_id', p_replacement_ruleset_id)
  from public.clinical_safety_releases release
  where release.status = 'active'
    and not exists (
      select 1 from public.clinical_safety_ruleset_members member
      where member.ruleset_id = p_replacement_ruleset_id
        and member.release_id = release.id
    );

  update public.clinical_safety_releases release
  set status = 'rolled_back', terminal_reason = p_reason
  where release.status = 'active'
    and not exists (
      select 1 from public.clinical_safety_ruleset_members member
      where member.ruleset_id = p_replacement_ruleset_id
        and member.release_id = release.id
    );

  update public.clinical_safety_rulesets
  set status = 'rolled_back', terminal_reason = p_reason
  where id = p_active_ruleset_id;

  update public.clinical_safety_releases release
  set status = 'active', terminal_reason = null
  where release.id in (
    select member.release_id
    from public.clinical_safety_ruleset_members member
    where member.ruleset_id = p_replacement_ruleset_id
  );

  update public.clinical_safety_rulesets
  set status = 'active', terminal_reason = null
  where id = p_replacement_ruleset_id;

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
    'ruleset_rolled_back',
    'ruleset',
    p_active_ruleset_id,
    v_now,
    p_reason,
    'active',
    'rolled_back',
    v_active.manifest_digest,
    jsonb_build_object('replacement_ruleset_id', p_replacement_ruleset_id)
  );

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
    'ruleset_activated',
    'ruleset',
    p_replacement_ruleset_id,
    v_now,
    'Rollback replacement activated: ' || p_reason,
    v_replacement.status,
    'active',
    v_replacement.manifest_digest,
    jsonb_build_object('rolled_back_ruleset_id', p_active_ruleset_id)
  );

  if exists (
    select 1 from public.clinical_safety_releases release
    where release.status = 'active'
      and not exists (
        select 1 from public.clinical_safety_ruleset_members member
        where member.ruleset_id = p_replacement_ruleset_id
          and member.release_id = release.id
      )
  ) or exists (
    select 1 from public.clinical_safety_ruleset_members member
    left join public.clinical_safety_releases release on release.id = member.release_id
    where member.ruleset_id = p_replacement_ruleset_id
      and (release.id is null or release.status <> 'active')
  ) then
    raise exception 'Atomic ruleset rollback failed final consistency check'
      using errcode = '42501';
  end if;

  return p_replacement_ruleset_id;
end;
$$;

revoke all on function public.approve_janani_clinical_safety_ruleset(
  uuid, text, text[], uuid[], timestamptz, timestamptz, uuid
) from public, anon, authenticated;
revoke all on function public.activate_janani_clinical_safety_ruleset(uuid, text)
from public, anon, authenticated;
revoke all on function public.rollback_janani_clinical_safety_ruleset(uuid, uuid, text)
from public, anon, authenticated;

grant execute on function public.approve_janani_clinical_safety_ruleset(
  uuid, text, text[], uuid[], timestamptz, timestamptz, uuid
) to service_role;
grant execute on function public.activate_janani_clinical_safety_ruleset(uuid, text)
to service_role;
grant execute on function public.rollback_janani_clinical_safety_ruleset(uuid, uuid, text)
to service_role;

comment on table public.clinical_safety_rulesets is
  'Immutable deployable manifests for complete deterministic clinical-safety rulesets.';
comment on table public.clinical_safety_ruleset_members is
  'Immutable release membership bound to a complete clinical-safety ruleset manifest.';
comment on function public.activate_janani_clinical_safety_ruleset is
  'Service-role-only atomic replacement of the complete active deterministic safety ruleset.';
comment on function public.rollback_janani_clinical_safety_ruleset is
  'Service-role-only atomic rollback to a complete prior deterministic safety ruleset.';
