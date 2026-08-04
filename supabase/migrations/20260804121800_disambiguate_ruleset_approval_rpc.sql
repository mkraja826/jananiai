-- Keep the strongly typed approval transaction internal and expose exactly one
-- PostgREST-compatible public RPC signature.

alter function public.approve_janani_clinical_safety_ruleset(
  uuid, text, text[], uuid[], timestamptz, timestamptz, uuid
) rename to approve_janani_clinical_safety_ruleset_internal;

drop function if exists public.approve_janani_clinical_safety_ruleset(jsonb);

create function public.approve_janani_clinical_safety_ruleset(jsonb)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_payload jsonb := $1;
  v_supersedes_ruleset_id uuid;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if v_payload is null or jsonb_typeof(v_payload) <> 'object' then
    raise exception 'Ruleset approval payload must be a JSON object'
      using errcode = '22023';
  end if;

  if v_payload ? 'p_supersedes_ruleset_id'
    and v_payload ->> 'p_supersedes_ruleset_id' is not null
  then
    v_supersedes_ruleset_id := (v_payload ->> 'p_supersedes_ruleset_id')::uuid;
  end if;

  return public.approve_janani_clinical_safety_ruleset_internal(
    (v_payload ->> 'p_ruleset_id')::uuid,
    v_payload ->> 'p_version',
    array(
      select value
      from jsonb_array_elements_text(v_payload -> 'p_required_rule_ids') value
    ),
    array(
      select value::uuid
      from jsonb_array_elements_text(v_payload -> 'p_release_ids') value
    ),
    (v_payload ->> 'p_activates_at')::timestamptz,
    (v_payload ->> 'p_expires_at')::timestamptz,
    v_supersedes_ruleset_id
  );
end;
$$;

revoke all on function public.approve_janani_clinical_safety_ruleset(jsonb)
from public, anon, authenticated;
grant execute on function public.approve_janani_clinical_safety_ruleset(jsonb)
to service_role;

revoke all on function public.approve_janani_clinical_safety_ruleset_internal(
  uuid, text, text[], uuid[], timestamptz, timestamptz, uuid
) from public, anon, authenticated;
grant execute on function public.approve_janani_clinical_safety_ruleset_internal(
  uuid, text, text[], uuid[], timestamptz, timestamptz, uuid
) to service_role;

notify pgrst, 'reload schema';
