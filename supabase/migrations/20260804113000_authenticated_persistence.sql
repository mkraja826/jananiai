-- Janani AI Phase 3: authenticated audit RPCs, attachment confirmation,
-- explicit table privileges, and account-deletion request foundations.

create unique index if not exists safety_audit_events_request_id_unique
  on public.safety_audit_events(request_id);

create table if not exists public.account_deletion_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users(id) on delete cascade,
  status text not null default 'pending' check (
    status in ('pending', 'processing', 'completed', 'cancelled')
  ),
  requested_at timestamptz not null default now(),
  processing_started_at timestamptz,
  completed_at timestamptz,
  cancelled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger set_account_deletion_requests_updated_at
before update on public.account_deletion_requests
for each row execute function public.set_updated_at();

alter table public.account_deletion_requests enable row level security;

create policy account_deletion_requests_select_own
on public.account_deletion_requests for select
to authenticated
using (auth.uid() = user_id);

revoke all on public.user_health_profiles from anon;
revoke all on public.pregnancies from anon;
revoke all on public.consent_events from anon;
revoke all on public.medication_records from anon;
revoke all on public.appointment_records from anon;
revoke all on public.attachment_records from anon;
revoke all on public.attachment_extractions from anon;
revoke all on public.context_assembly_events from anon;
revoke all on public.safety_audit_events from anon;
revoke all on public.account_deletion_requests from anon;

grant select, insert, update, delete on public.user_health_profiles to authenticated;
grant select, insert, update, delete on public.pregnancies to authenticated;
grant select, insert on public.consent_events to authenticated;
grant select, insert, update, delete on public.medication_records to authenticated;
grant select, insert, update, delete on public.appointment_records to authenticated;
grant select, insert, update, delete on public.attachment_records to authenticated;
grant select on public.attachment_extractions to authenticated;
grant select on public.context_assembly_events to authenticated;
grant select on public.safety_audit_events to authenticated;
grant select on public.account_deletion_requests to authenticated;

revoke update, delete on public.consent_events from authenticated;
revoke insert, update, delete on public.attachment_extractions from authenticated;
revoke insert, update, delete on public.context_assembly_events from authenticated;
revoke insert, update, delete on public.safety_audit_events from authenticated;
revoke insert, update, delete on public.account_deletion_requests from authenticated;

create or replace function public.record_janani_safety_event(
  p_request_id uuid,
  p_ruleset_version text,
  p_triggered_rule_ids text[],
  p_severity text,
  p_blocks_llm boolean,
  p_synthetic boolean
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_event_id uuid;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  insert into public.safety_audit_events (
    user_id,
    request_id,
    ruleset_version,
    triggered_rule_ids,
    severity,
    blocks_llm,
    synthetic
  )
  values (
    v_user_id,
    p_request_id,
    p_ruleset_version,
    coalesce(p_triggered_rule_ids, '{}'::text[]),
    p_severity,
    p_blocks_llm,
    p_synthetic
  )
  on conflict (request_id) do update
  set
    user_id = excluded.user_id,
    ruleset_version = excluded.ruleset_version,
    triggered_rule_ids = excluded.triggered_rule_ids,
    severity = excluded.severity,
    blocks_llm = excluded.blocks_llm,
    synthetic = excluded.synthetic
  returning id into v_event_id;

  return v_event_id;
end;
$$;

create or replace function public.record_janani_context_event(
  p_event_id uuid,
  p_task text,
  p_status text,
  p_safety_event_id uuid,
  p_selected_medication_ids uuid[],
  p_selected_appointment_ids uuid[],
  p_selected_attachment_ids uuid[],
  p_selected_knowledge_ids text[],
  p_excluded_item_count integer,
  p_schema_version text,
  p_synthetic boolean
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  insert into public.context_assembly_events (
    id,
    user_id,
    task,
    status,
    safety_event_id,
    selected_medication_ids,
    selected_appointment_ids,
    selected_attachment_ids,
    selected_knowledge_ids,
    excluded_item_count,
    schema_version,
    synthetic
  )
  values (
    p_event_id,
    v_user_id,
    p_task,
    p_status,
    p_safety_event_id,
    coalesce(p_selected_medication_ids, '{}'::uuid[]),
    coalesce(p_selected_appointment_ids, '{}'::uuid[]),
    coalesce(p_selected_attachment_ids, '{}'::uuid[]),
    coalesce(p_selected_knowledge_ids, '{}'::text[]),
    greatest(coalesce(p_excluded_item_count, 0), 0),
    p_schema_version,
    p_synthetic
  )
  on conflict (id) do nothing;

  return p_event_id;
end;
$$;

create or replace function public.confirm_janani_attachment_extraction(
  p_attachment_id uuid,
  p_extraction_id uuid,
  p_confirmation public.janani_confirmation_status
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if p_confirmation not in ('confirmed', 'rejected') then
    raise exception 'Invalid confirmation state' using errcode = '22023';
  end if;
  if not exists (
    select 1
    from public.attachment_records attachment
    join public.attachment_extractions extraction
      on extraction.attachment_id = attachment.id
    where attachment.id = p_attachment_id
      and attachment.user_id = v_user_id
      and extraction.id = p_extraction_id
  ) then
    raise exception 'Attachment extraction not found' using errcode = '42501';
  end if;

  update public.attachment_extractions
  set user_confirmed_at = case
    when p_confirmation = 'confirmed' then now()
    else null
  end
  where id = p_extraction_id and attachment_id = p_attachment_id;

  update public.attachment_records
  set confirmation_status = p_confirmation
  where id = p_attachment_id and user_id = v_user_id;
end;
$$;

create or replace function public.request_janani_account_deletion()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_request public.account_deletion_requests%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  insert into public.account_deletion_requests (
    user_id,
    status,
    requested_at,
    processing_started_at,
    completed_at,
    cancelled_at
  )
  values (v_user_id, 'pending', now(), null, null, null)
  on conflict (user_id) do update
  set
    status = 'pending',
    requested_at = now(),
    processing_started_at = null,
    completed_at = null,
    cancelled_at = null
  returning * into v_request;

  return jsonb_build_object(
    'request_id', v_request.id,
    'status', v_request.status
  );
end;
$$;

revoke all on function public.record_janani_safety_event(
  uuid, text, text[], text, boolean, boolean
) from public, anon;
revoke all on function public.record_janani_context_event(
  uuid, text, text, uuid, uuid[], uuid[], uuid[], text[], integer, text, boolean
) from public, anon;
revoke all on function public.confirm_janani_attachment_extraction(
  uuid, uuid, public.janani_confirmation_status
) from public, anon;
revoke all on function public.request_janani_account_deletion() from public, anon;

grant execute on function public.record_janani_safety_event(
  uuid, text, text[], text, boolean, boolean
) to authenticated;
grant execute on function public.record_janani_context_event(
  uuid, text, text, uuid, uuid[], uuid[], uuid[], text[], integer, text, boolean
) to authenticated;
grant execute on function public.confirm_janani_attachment_extraction(
  uuid, uuid, public.janani_confirmation_status
) to authenticated;
grant execute on function public.request_janani_account_deletion() to authenticated;

comment on table public.account_deletion_requests is
  'One authenticated deletion workflow record per user; actual deletion is a later controlled job.';
comment on function public.record_janani_safety_event is
  'Writes a minimal safety audit event using auth.uid(); raw symptoms and notes are excluded.';
comment on function public.record_janani_context_event is
  'Writes selected IDs and status only; questions, report text, prompts, and outputs are excluded.';
