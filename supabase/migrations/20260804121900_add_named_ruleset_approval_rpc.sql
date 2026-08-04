-- Explicit named JSON RPC for PostgREST compatibility.
-- The public endpoint accepts one named object and delegates to the existing
-- strongly typed, service-role-only transaction.

create or replace function public.approve_janani_clinical_safety_ruleset_rpc(
  p_payload jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_supersedes_ruleset_id uuid;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception 'Ruleset approval payload must be a JSON object'
      using errcode = '22023';
  end if;

  if p_payload ? 'p_supersedes_ruleset_id'
    and p_payload ->> 'p_supersedes_ruleset_id' is not null
  then
    v_supersedes_ruleset_id := (p_payload ->> 'p_supersedes_ruleset_id')::uuid;
  end if;

  return public.approve_janani_clinical_safety_ruleset_internal(
    (p_payload ->> 'p_ruleset_id')::uuid,
    p_payload ->> 'p_version',
    array(
      select value
      from jsonb_array_elements_text(p_payload -> 'p_required_rule_ids') value
    ),
    array(
      select value::uuid
      from jsonb_array_elements_text(p_payload -> 'p_release_ids') value
    ),
    (p_payload ->> 'p_activates_at')::timestamptz,
    (p_payload ->> 'p_expires_at')::timestamptz,
    v_supersedes_ruleset_id
  );
end;
$$;

revoke all on function public.approve_janani_clinical_safety_ruleset_rpc(jsonb)
from public, anon, authenticated;
grant execute on function public.approve_janani_clinical_safety_ruleset_rpc(jsonb)
to service_role;

notify pgrst, 'reload schema';
