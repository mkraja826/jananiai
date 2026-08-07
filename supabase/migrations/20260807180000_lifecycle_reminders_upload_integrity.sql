-- Janani AI Phase 9: pregnancy completion lifecycle, explicit user-configured
-- reminders, and one-time attachment upload/integrity handshakes.
-- This migration stores facts and schedules only. It does not infer medication timing,
-- interpret clinical values, or make treatment decisions.

create table if not exists public.pregnancy_completion_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  pregnancy_id uuid not null references public.pregnancies(id) on delete cascade,
  occurred_at timestamptz not null,
  completion_type text not null check (
    completion_type in ('delivery', 'pregnancy_loss', 'other')
  ),
  source text not null check (source in ('user_entered', 'clinician_entered')),
  confirmed boolean not null default false,
  note text check (note is null or length(note) <= 1000),
  supersedes_completion_event_id uuid references public.pregnancy_completion_events(id) on delete restrict,
  synthetic boolean not null default true,
  created_at timestamptz not null default now(),
  constraint pregnancy_completion_not_self_superseding check (
    supersedes_completion_event_id is null or supersedes_completion_event_id <> id
  )
);

create unique index if not exists pregnancy_completion_single_supersession_idx
  on public.pregnancy_completion_events(supersedes_completion_event_id)
  where supersedes_completion_event_id is not null;
create index if not exists pregnancy_completion_user_pregnancy_time_idx
  on public.pregnancy_completion_events(user_id, pregnancy_id, occurred_at desc);

create table if not exists public.medication_reminder_schedules (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  medication_id uuid not null references public.medication_records(id) on delete cascade,
  local_time time not null,
  timezone_name text not null check (length(timezone_name) between 1 and 64),
  start_date date not null,
  end_date date,
  weekdays smallint[] not null default array[1,2,3,4,5,6,7]::smallint[],
  enabled boolean not null default true,
  disabled_at timestamptz,
  synthetic boolean not null default true,
  created_at timestamptz not null default now(),
  constraint medication_reminder_date_range_check check (
    end_date is null or end_date >= start_date
  ),
  constraint medication_reminder_weekdays_check check (
    cardinality(weekdays) between 1 and 7
    and weekdays <@ array[1,2,3,4,5,6,7]::smallint[]
  ),
  constraint medication_reminder_disabled_state_check check (
    (enabled and disabled_at is null) or (not enabled and disabled_at is not null)
  )
);

create unique index if not exists medication_reminder_active_unique_idx
  on public.medication_reminder_schedules(
    user_id,
    medication_id,
    local_time,
    timezone_name,
    start_date,
    weekdays
  )
  where enabled;
create index if not exists medication_reminder_user_created_idx
  on public.medication_reminder_schedules(user_id, created_at desc);

create table if not exists public.appointment_reminder_schedules (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  appointment_id uuid not null references public.appointment_records(id) on delete cascade,
  lead_minutes integer not null check (lead_minutes between 0 and 43200),
  enabled boolean not null default true,
  disabled_at timestamptz,
  synthetic boolean not null default true,
  created_at timestamptz not null default now(),
  constraint appointment_reminder_disabled_state_check check (
    (enabled and disabled_at is null) or (not enabled and disabled_at is not null)
  )
);

create unique index if not exists appointment_reminder_active_unique_idx
  on public.appointment_reminder_schedules(user_id, appointment_id, lead_minutes)
  where enabled;
create index if not exists appointment_reminder_user_created_idx
  on public.appointment_reminder_schedules(user_id, created_at desc);

create table if not exists public.attachment_upload_intents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  pregnancy_id uuid references public.pregnancies(id) on delete cascade,
  kind public.janani_attachment_kind not null,
  mime_type text not null check (
    mime_type in ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
  ),
  file_size_bytes bigint not null check (
    file_size_bytes > 0 and file_size_bytes <= 20971520
  ),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  document_date date,
  display_label text check (display_label is null or length(display_label) between 1 and 120),
  capture_source text not null check (
    capture_source in ('camera', 'file_upload', 'scan_import', 'other')
  ),
  bucket_id text not null default 'janani-private' check (bucket_id = 'janani-private'),
  storage_object_path text not null unique,
  status text not null default 'pending' check (
    status in ('pending', 'completed', 'expired', 'cancelled')
  ),
  expires_at timestamptz not null,
  completed_at timestamptz,
  synthetic boolean not null default true,
  created_at timestamptz not null default now(),
  constraint attachment_upload_intent_owner_path_check check (
    storage_object_path like user_id::text || '/%'
  ),
  constraint attachment_upload_intent_state_check check (
    (status = 'completed' and completed_at is not null)
    or (status <> 'completed' and completed_at is null)
  )
);

create index if not exists attachment_upload_intents_user_created_idx
  on public.attachment_upload_intents(user_id, created_at desc);
create index if not exists attachment_upload_intents_pending_expiry_idx
  on public.attachment_upload_intents(expires_at)
  where status = 'pending';

alter table public.attachment_records
  add column if not exists upload_intent_id uuid references public.attachment_upload_intents(id) on delete restrict,
  add column if not exists integrity_status text not null default 'unverified',
  add column if not exists integrity_verified_at timestamptz;

alter table public.attachment_records
  add constraint attachment_integrity_status_check check (
    integrity_status in ('unverified', 'pending_worker_hash', 'verified', 'mismatch')
  ),
  add constraint attachment_integrity_verified_state_check check (
    (integrity_status = 'verified' and integrity_verified_at is not null)
    or (integrity_status <> 'verified' and integrity_verified_at is null)
  );

create unique index if not exists attachment_records_upload_intent_unique_idx
  on public.attachment_records(upload_intent_id)
  where upload_intent_id is not null;

alter table public.pregnancy_completion_events enable row level security;
alter table public.medication_reminder_schedules enable row level security;
alter table public.appointment_reminder_schedules enable row level security;
alter table public.attachment_upload_intents enable row level security;

create policy pregnancy_completion_events_select_own
on public.pregnancy_completion_events for select
to authenticated
using ((select auth.uid()) = user_id);

create policy medication_reminder_schedules_select_own
on public.medication_reminder_schedules for select
to authenticated
using ((select auth.uid()) = user_id);

create policy appointment_reminder_schedules_select_own
on public.appointment_reminder_schedules for select
to authenticated
using ((select auth.uid()) = user_id);

create policy attachment_upload_intents_select_own
on public.attachment_upload_intents for select
to authenticated
using ((select auth.uid()) = user_id);

revoke all on public.pregnancy_completion_events from anon, authenticated;
revoke all on public.medication_reminder_schedules from anon, authenticated;
revoke all on public.appointment_reminder_schedules from anon, authenticated;
revoke all on public.attachment_upload_intents from anon, authenticated;
grant select on public.pregnancy_completion_events to authenticated;
grant select on public.medication_reminder_schedules to authenticated;
grant select on public.appointment_reminder_schedules to authenticated;
grant select on public.attachment_upload_intents to authenticated;
grant all on public.pregnancy_completion_events to service_role;
grant all on public.medication_reminder_schedules to service_role;
grant all on public.appointment_reminder_schedules to service_role;
grant all on public.attachment_upload_intents to service_role;

-- Finalized attachment rows must be created through the one-time upload handshake.
-- Existing rows remain readable but cannot be mutated directly by authenticated users.
revoke insert, update, delete on public.attachment_records from authenticated;

-- Keep the private bucket suitable for reports/prescriptions while remaining within a
-- conservative app-level limit. Supabase's project-level limit can be lower and still wins.
update storage.buckets
set
  file_size_limit = 20971520,
  allowed_mime_types = array[
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/webp'
  ]::text[]
where id = 'janani-private';

-- After an attachment is finalized, authenticated clients may read it but cannot overwrite
-- or delete that exact object path. Unfinalized/orphan objects remain user-cleanable.
drop policy if exists janani_private_storage_update_own on storage.objects;
create policy janani_private_storage_update_own
on storage.objects for update
to authenticated
using (
  bucket_id = 'janani-private'
  and (storage.foldername(name))[1] = (select auth.uid())::text
  and not exists (
    select 1
    from public.attachment_records attachment
    where attachment.user_id = (select auth.uid())
      and attachment.storage_object_path = name
  )
)
with check (
  bucket_id = 'janani-private'
  and (storage.foldername(name))[1] = (select auth.uid())::text
  and not exists (
    select 1
    from public.attachment_records attachment
    where attachment.user_id = (select auth.uid())
      and attachment.storage_object_path = name
  )
);

drop policy if exists janani_private_storage_delete_own on storage.objects;
create policy janani_private_storage_delete_own
on storage.objects for delete
to authenticated
using (
  bucket_id = 'janani-private'
  and (storage.foldername(name))[1] = (select auth.uid())::text
  and not exists (
    select 1
    from public.attachment_records attachment
    where attachment.user_id = (select auth.uid())
      and attachment.storage_object_path = name
  )
);

create or replace function public.record_janani_pregnancy_completion(
  p_pregnancy_id uuid,
  p_occurred_at timestamptz,
  p_completion_type text,
  p_source text,
  p_confirmed boolean,
  p_note text,
  p_supersedes_completion_event_id uuid,
  p_synthetic boolean
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_pregnancy_status text;
  v_event public.pregnancy_completion_events%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if p_completion_type not in ('delivery', 'pregnancy_loss', 'other') then
    raise exception 'Unsupported pregnancy completion type' using errcode = '22023';
  end if;
  if p_source not in ('user_entered', 'clinician_entered') then
    raise exception 'Unsupported pregnancy completion source' using errcode = '22023';
  end if;
  if p_note is not null and length(p_note) > 1000 then
    raise exception 'Pregnancy completion note is too long' using errcode = '22023';
  end if;

  select pregnancy.status
  into v_pregnancy_status
  from public.pregnancies pregnancy
  where pregnancy.id = p_pregnancy_id
    and pregnancy.user_id = v_user_id
  for update;

  if v_pregnancy_status is null then
    raise exception 'Pregnancy episode not found' using errcode = '42501';
  end if;

  if p_supersedes_completion_event_id is null then
    if v_pregnancy_status <> 'active' then
      raise exception 'Only an active pregnancy can receive its first completion event'
        using errcode = '22023';
    end if;
    if exists (
      select 1 from public.pregnancy_completion_events existing
      where existing.user_id = v_user_id
        and existing.pregnancy_id = p_pregnancy_id
    ) then
      raise exception 'Existing completion must be corrected through supersession'
        using errcode = '22023';
    end if;
  else
    if v_pregnancy_status <> 'completed' then
      raise exception 'Completion correction requires a completed pregnancy'
        using errcode = '22023';
    end if;
    if not exists (
      select 1 from public.pregnancy_completion_events previous
      where previous.id = p_supersedes_completion_event_id
        and previous.user_id = v_user_id
        and previous.pregnancy_id = p_pregnancy_id
    ) then
      raise exception 'Superseded completion event not found' using errcode = '42501';
    end if;
  end if;

  insert into public.pregnancy_completion_events (
    user_id,
    pregnancy_id,
    occurred_at,
    completion_type,
    source,
    confirmed,
    note,
    supersedes_completion_event_id,
    synthetic
  )
  values (
    v_user_id,
    p_pregnancy_id,
    p_occurred_at,
    p_completion_type,
    p_source,
    coalesce(p_confirmed, false),
    p_note,
    p_supersedes_completion_event_id,
    coalesce(p_synthetic, true)
  )
  returning * into v_event;

  update public.pregnancies
  set
    status = 'completed',
    completed_at = p_occurred_at
  where id = p_pregnancy_id
    and user_id = v_user_id;

  return to_jsonb(v_event);
end;
$$;

create or replace function public.create_janani_medication_reminder(
  p_medication_id uuid,
  p_local_time time,
  p_timezone_name text,
  p_start_date date,
  p_end_date date,
  p_weekdays smallint[],
  p_synthetic boolean
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_user_id uuid := auth.uid();
  v_reminder public.medication_reminder_schedules%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if p_timezone_name is null or not exists (
    select 1 from pg_catalog.pg_timezone_names zone where zone.name = p_timezone_name
  ) then
    raise exception 'Invalid IANA timezone name' using errcode = '22023';
  end if;
  if p_start_date is null or (p_end_date is not null and p_end_date < p_start_date) then
    raise exception 'Invalid reminder date range' using errcode = '22023';
  end if;
  if p_weekdays is null
    or cardinality(p_weekdays) not between 1 and 7
    or not (p_weekdays <@ array[1,2,3,4,5,6,7]::smallint[])
    or exists (
      select 1
      from unnest(p_weekdays) as weekday(value)
      group by weekday.value
      having count(*) > 1
    )
  then
    raise exception 'Weekdays must be unique ISO weekday numbers 1 through 7'
      using errcode = '22023';
  end if;
  if not exists (
    select 1
    from public.medication_records medication
    where medication.id = p_medication_id
      and medication.user_id = v_user_id
      and medication.active
      and medication.confirmed
  ) then
    raise exception 'Medication must be owned, active, and confirmed before reminders are enabled'
      using errcode = '42501';
  end if;

  insert into public.medication_reminder_schedules (
    user_id,
    medication_id,
    local_time,
    timezone_name,
    start_date,
    end_date,
    weekdays,
    synthetic
  )
  values (
    v_user_id,
    p_medication_id,
    p_local_time,
    p_timezone_name,
    p_start_date,
    p_end_date,
    p_weekdays,
    coalesce(p_synthetic, true)
  )
  returning * into v_reminder;

  return to_jsonb(v_reminder);
end;
$$;

create or replace function public.create_janani_appointment_reminder(
  p_appointment_id uuid,
  p_lead_minutes integer,
  p_synthetic boolean
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_reminder public.appointment_reminder_schedules%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if p_lead_minutes is null or p_lead_minutes < 0 or p_lead_minutes > 43200 then
    raise exception 'Reminder lead_minutes must be between 0 and 43200'
      using errcode = '22023';
  end if;
  if not exists (
    select 1
    from public.appointment_records appointment
    where appointment.id = p_appointment_id
      and appointment.user_id = v_user_id
      and appointment.status = 'scheduled'
  ) then
    raise exception 'Appointment must be owned and scheduled before reminders are enabled'
      using errcode = '42501';
  end if;

  insert into public.appointment_reminder_schedules (
    user_id,
    appointment_id,
    lead_minutes,
    synthetic
  )
  values (
    v_user_id,
    p_appointment_id,
    p_lead_minutes,
    coalesce(p_synthetic, true)
  )
  returning * into v_reminder;

  return to_jsonb(v_reminder);
end;
$$;

create or replace function public.disable_janani_reminder(
  p_reminder_kind text,
  p_reminder_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_medication public.medication_reminder_schedules%rowtype;
  v_appointment public.appointment_reminder_schedules%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  if p_reminder_kind = 'medication' then
    update public.medication_reminder_schedules
    set enabled = false, disabled_at = coalesce(disabled_at, now())
    where id = p_reminder_id
      and user_id = v_user_id
    returning * into v_medication;

    if v_medication.id is null then
      raise exception 'Medication reminder not found' using errcode = '42501';
    end if;
    return to_jsonb(v_medication);
  elsif p_reminder_kind = 'appointment' then
    update public.appointment_reminder_schedules
    set enabled = false, disabled_at = coalesce(disabled_at, now())
    where id = p_reminder_id
      and user_id = v_user_id
    returning * into v_appointment;

    if v_appointment.id is null then
      raise exception 'Appointment reminder not found' using errcode = '42501';
    end if;
    return to_jsonb(v_appointment);
  end if;

  raise exception 'Unsupported reminder kind' using errcode = '22023';
end;
$$;

create or replace function public.request_janani_attachment_upload(
  p_pregnancy_id uuid,
  p_kind text,
  p_mime_type text,
  p_file_size_bytes bigint,
  p_content_sha256 text,
  p_document_date date,
  p_display_label text,
  p_capture_source text,
  p_synthetic boolean
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_intent_id uuid := gen_random_uuid();
  v_intent public.attachment_upload_intents%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if p_kind not in (
    'lab_report', 'ultrasound_report', 'prescription', 'discharge_summary', 'other_document'
  ) then
    raise exception 'Unsupported attachment kind' using errcode = '22023';
  end if;
  if lower(coalesce(p_mime_type, '')) not in (
    'application/pdf', 'image/jpeg', 'image/png', 'image/webp'
  ) then
    raise exception 'Unsupported attachment MIME type' using errcode = '22023';
  end if;
  if p_file_size_bytes is null or p_file_size_bytes <= 0 or p_file_size_bytes > 20971520 then
    raise exception 'Attachment size must be between 1 byte and 20 MiB'
      using errcode = '22023';
  end if;
  if lower(coalesce(p_content_sha256, '')) !~ '^[0-9a-f]{64}$' then
    raise exception 'A lowercase SHA-256 content digest is required' using errcode = '22023';
  end if;
  if p_capture_source not in ('camera', 'file_upload', 'scan_import', 'other') then
    raise exception 'Unsupported attachment capture source' using errcode = '22023';
  end if;
  if p_display_label is not null and length(p_display_label) not between 1 and 120 then
    raise exception 'Attachment display label is invalid' using errcode = '22023';
  end if;
  if p_pregnancy_id is not null and not exists (
    select 1
    from public.pregnancies pregnancy
    where pregnancy.id = p_pregnancy_id
      and pregnancy.user_id = v_user_id
  ) then
    raise exception 'Pregnancy episode not found' using errcode = '42501';
  end if;

  insert into public.attachment_upload_intents (
    id,
    user_id,
    pregnancy_id,
    kind,
    mime_type,
    file_size_bytes,
    content_sha256,
    document_date,
    display_label,
    capture_source,
    bucket_id,
    storage_object_path,
    expires_at,
    synthetic
  )
  values (
    v_intent_id,
    v_user_id,
    p_pregnancy_id,
    p_kind::public.janani_attachment_kind,
    lower(p_mime_type),
    p_file_size_bytes,
    lower(p_content_sha256),
    p_document_date,
    p_display_label,
    p_capture_source,
    'janani-private',
    v_user_id::text || '/uploads/' || v_intent_id::text,
    now() + interval '15 minutes',
    coalesce(p_synthetic, true)
  )
  returning * into v_intent;

  return to_jsonb(v_intent);
end;
$$;

create or replace function public.finalize_janani_attachment_upload(
  p_intent_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public, storage
as $$
declare
  v_user_id uuid := auth.uid();
  v_intent public.attachment_upload_intents%rowtype;
  v_attachment public.attachment_records%rowtype;
  v_storage_metadata jsonb;
  v_storage_size bigint;
  v_storage_mime text;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  select *
  into v_intent
  from public.attachment_upload_intents intent
  where intent.id = p_intent_id
    and intent.user_id = v_user_id
  for update;

  if v_intent.id is null then
    raise exception 'Attachment upload intent not found' using errcode = '42501';
  end if;

  if v_intent.status = 'completed' then
    select *
    into v_attachment
    from public.attachment_records attachment
    where attachment.upload_intent_id = v_intent.id
      and attachment.user_id = v_user_id;
    if v_attachment.id is null then
      raise exception 'Completed upload intent is missing its attachment record'
        using errcode = 'P0002';
    end if;
    return to_jsonb(v_attachment);
  end if;

  if v_intent.status <> 'pending' then
    raise exception 'Attachment upload intent is no longer pending' using errcode = '22023';
  end if;
  if now() > v_intent.expires_at then
    raise exception 'Attachment upload intent has expired' using errcode = '22023';
  end if;

  select object.metadata
  into v_storage_metadata
  from storage.objects object
  where object.bucket_id = v_intent.bucket_id
    and object.name = v_intent.storage_object_path;

  if v_storage_metadata is null then
    raise exception 'Uploaded Storage object was not found' using errcode = '22023';
  end if;

  begin
    v_storage_size := (v_storage_metadata ->> 'size')::bigint;
  exception when others then
    raise exception 'Uploaded Storage object has invalid size metadata' using errcode = '22023';
  end;
  v_storage_mime := lower(coalesce(v_storage_metadata ->> 'mimetype', ''));

  if v_storage_size <> v_intent.file_size_bytes then
    raise exception 'Uploaded Storage object size does not match upload intent'
      using errcode = '22023';
  end if;
  if v_storage_mime <> v_intent.mime_type then
    raise exception 'Uploaded Storage object MIME type does not match upload intent'
      using errcode = '22023';
  end if;

  insert into public.attachment_records (
    user_id,
    pregnancy_id,
    kind,
    mime_type,
    storage_object_path,
    document_date,
    display_label,
    capture_source,
    file_size_bytes,
    content_sha256,
    synthetic,
    upload_intent_id,
    integrity_status
  )
  values (
    v_user_id,
    v_intent.pregnancy_id,
    v_intent.kind,
    v_intent.mime_type,
    v_intent.storage_object_path,
    v_intent.document_date,
    v_intent.display_label,
    v_intent.capture_source,
    v_intent.file_size_bytes,
    v_intent.content_sha256,
    v_intent.synthetic,
    v_intent.id,
    'pending_worker_hash'
  )
  returning * into v_attachment;

  update public.attachment_upload_intents
  set status = 'completed', completed_at = now()
  where id = v_intent.id;

  return to_jsonb(v_attachment);
end;
$$;

create or replace function public.verify_janani_attachment_integrity(
  p_attachment_id uuid,
  p_actual_sha256 text
)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_expected_sha256 text;
  v_status text;
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if lower(coalesce(p_actual_sha256, '')) !~ '^[0-9a-f]{64}$' then
    raise exception 'A valid SHA-256 content digest is required' using errcode = '22023';
  end if;

  select lower(attachment.content_sha256)
  into v_expected_sha256
  from public.attachment_records attachment
  where attachment.id = p_attachment_id;

  if v_expected_sha256 is null then
    raise exception 'Attachment not found or has no expected SHA-256 digest'
      using errcode = 'P0002';
  end if;

  v_status := case
    when v_expected_sha256 = lower(p_actual_sha256) then 'verified'
    else 'mismatch'
  end;

  update public.attachment_records
  set
    integrity_status = v_status,
    integrity_verified_at = case when v_status = 'verified' then now() else null end
  where id = p_attachment_id;

  return v_status;
end;
$$;

-- Extraction is now gated on a successful backend hash verification.
create or replace function public.record_janani_attachment_extraction(
  p_extraction_id uuid,
  p_attachment_id uuid,
  p_extractor_name text,
  p_extractor_version text,
  p_extracted_text text,
  p_confidence numeric
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
begin
  if auth.role() <> 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;

  if not exists (
    select 1
    from public.attachment_records attachment
    where attachment.id = p_attachment_id
      and attachment.integrity_status = 'verified'
  ) then
    raise exception 'Attachment integrity must be verified before extraction'
      using errcode = '42501';
  end if;

  if p_extractor_name is null or length(trim(p_extractor_name)) = 0 then
    raise exception 'Extractor name is required' using errcode = '22023';
  end if;
  if p_extractor_version is null or length(trim(p_extractor_version)) = 0 then
    raise exception 'Extractor version is required' using errcode = '22023';
  end if;
  if p_extracted_text is null or length(trim(p_extracted_text)) = 0 then
    raise exception 'Extracted text is required' using errcode = '22023';
  end if;
  if p_confidence is not null and (p_confidence < 0 or p_confidence > 1) then
    raise exception 'Extraction confidence must be between 0 and 1'
      using errcode = '22023';
  end if;

  insert into public.attachment_extractions (
    id,
    attachment_id,
    extractor_name,
    extractor_version,
    extracted_text,
    confidence,
    user_confirmed_at
  )
  values (
    p_extraction_id,
    p_attachment_id,
    p_extractor_name,
    p_extractor_version,
    p_extracted_text,
    p_confidence,
    null
  )
  on conflict (id) do update
  set
    attachment_id = excluded.attachment_id,
    extractor_name = excluded.extractor_name,
    extractor_version = excluded.extractor_version,
    extracted_text = excluded.extracted_text,
    confidence = excluded.confidence,
    user_confirmed_at = null;

  update public.attachment_records
  set
    extraction_status = 'completed',
    confirmation_status = 'unconfirmed',
    latest_extraction_confidence = p_confidence
  where id = p_attachment_id;

  return p_extraction_id;
end;
$$;

revoke all on function public.record_janani_pregnancy_completion(
  uuid, timestamptz, text, text, boolean, text, uuid, boolean
) from public, anon;
grant execute on function public.record_janani_pregnancy_completion(
  uuid, timestamptz, text, text, boolean, text, uuid, boolean
) to authenticated;

revoke all on function public.create_janani_medication_reminder(
  uuid, time, text, date, date, smallint[], boolean
) from public, anon;
grant execute on function public.create_janani_medication_reminder(
  uuid, time, text, date, date, smallint[], boolean
) to authenticated;

revoke all on function public.create_janani_appointment_reminder(
  uuid, integer, boolean
) from public, anon;
grant execute on function public.create_janani_appointment_reminder(
  uuid, integer, boolean
) to authenticated;

revoke all on function public.disable_janani_reminder(text, uuid) from public, anon;
grant execute on function public.disable_janani_reminder(text, uuid) to authenticated;

revoke all on function public.request_janani_attachment_upload(
  uuid, text, text, bigint, text, date, text, text, boolean
) from public, anon;
grant execute on function public.request_janani_attachment_upload(
  uuid, text, text, bigint, text, date, text, text, boolean
) to authenticated;

revoke all on function public.finalize_janani_attachment_upload(uuid) from public, anon;
grant execute on function public.finalize_janani_attachment_upload(uuid) to authenticated;

revoke all on function public.verify_janani_attachment_integrity(uuid, text)
from public, anon, authenticated;
grant execute on function public.verify_janani_attachment_integrity(uuid, text) to service_role;

revoke all on function public.record_janani_attachment_extraction(
  uuid, uuid, text, text, text, numeric
) from public, anon, authenticated;
grant execute on function public.record_janani_attachment_extraction(
  uuid, uuid, text, text, text, numeric
) to service_role;

comment on table public.pregnancy_completion_events is
  'Append-only pregnancy completion facts. Corrections supersede prior events; no clinical interpretation is stored.';
comment on table public.medication_reminder_schedules is
  'User-configured medication reminder times. Timing is never inferred from dose or prescription text.';
comment on table public.appointment_reminder_schedules is
  'User-configured appointment reminder offsets for owned scheduled appointments.';
comment on table public.attachment_upload_intents is
  'Short-lived owner-scoped upload intents. Finalization verifies Storage size and MIME before attachment registration.';
comment on column public.attachment_records.integrity_status is
  'Cryptographic file integrity is verified only when a backend worker hashes the immutable finalized object.';
comment on function public.verify_janani_attachment_integrity is
  'Service-role-only SHA-256 verification step required before extraction.';
