-- Fix ambiguous JSON step extraction in the synthetic safety-rehearsal RPC.
-- Also require every recorded step and the top-level rehearsal result to pass.

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
  if coalesce((p_payload ->> 'passed')::boolean, false) is not true then
    raise exception 'Only fully passing synthetic rehearsals may be recorded'
      using errcode = '42501';
  end if;
  if jsonb_typeof(p_payload -> 'steps') <> 'array' then
    raise exception 'Rehearsal steps must be a JSON array' using errcode = '22023';
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

  select array_agg(step_item ->> 'name' order by step_item ->> 'name')
  into v_step_names
  from jsonb_array_elements(p_payload -> 'steps') as step_rows(step_item);

  if cardinality(v_step_names) <> 6
    or cardinality(v_step_names) <> (
      select count(distinct step_name)
      from unnest(v_step_names) as step_names(step_name)
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

  if exists (
    select 1
    from jsonb_array_elements(p_payload -> 'steps') as step_rows(step_item)
    where coalesce((step_item ->> 'passed')::boolean, false) is not true
      or nullif(trim(step_item ->> 'evidence_ref'), '') is null
  ) then
    raise exception 'Every rehearsal step must pass and contain evidence'
      using errcode = '42501';
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
    true,
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
      'passed', true,
      'active_ruleset_before', v_active_ruleset,
      'restored_ruleset_after', v_restored_ruleset
    )
  );

  return v_rehearsal_id;
end;
$$;

revoke all on function public.record_janani_safety_rehearsal(uuid, jsonb)
from public, anon, authenticated;
grant execute on function public.record_janani_safety_rehearsal(uuid, jsonb)
to service_role;

notify pgrst, 'reload schema';
