-- Expose one PostgREST-friendly approval signature whose named parameters
-- exactly match the JSON request keys. Validation and writes remain delegated
-- to the strongly typed internal transaction.

drop function if exists public.approve_janani_clinical_safety_ruleset(jsonb);
drop function if exists public.approve_janani_clinical_safety_ruleset_rpc(jsonb);

create function public.approve_janani_clinical_safety_ruleset(
  p_ruleset_id text,
  p_version text,
  p_required_rule_ids jsonb,
  p_release_ids jsonb,
  p_activates_at text,
  p_expires_at text,
  p_supersedes_ruleset_id text
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
  if jsonb_typeof(p_required_rule_ids) <> 'array'
    or jsonb_typeof(p_release_ids) <> 'array'
  then
    raise exception 'Ruleset rule IDs and release IDs must be JSON arrays'
      using errcode = '22023';
  end if;
  if p_supersedes_ruleset_id is not null then
    v_supersedes_ruleset_id := p_supersedes_ruleset_id::uuid;
  end if;

  return public.approve_janani_clinical_safety_ruleset_internal(
    p_ruleset_id::uuid,
    p_version,
    array(
      select value
      from jsonb_array_elements_text(p_required_rule_ids) value
    ),
    array(
      select value::uuid
      from jsonb_array_elements_text(p_release_ids) value
    ),
    p_activates_at::timestamptz,
    p_expires_at::timestamptz,
    v_supersedes_ruleset_id
  );
end;
$$;

revoke all on function public.approve_janani_clinical_safety_ruleset(
  text, text, jsonb, jsonb, text, text, text
) from public, anon, authenticated;
grant execute on function public.approve_janani_clinical_safety_ruleset(
  text, text, jsonb, jsonb, text, text, text
) to service_role;

notify pgrst, 'reload schema';
