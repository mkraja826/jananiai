-- Janani AI Phase 8: structured pregnancy episode metadata, append-only observations
-- and encounters, and stronger attachment metadata. This stores facts only; it does
-- not interpret measurements or provide clinical advice.

alter table public.pregnancies
  add column if not exists last_menstrual_period date,
  add column if not exists dating_source text not null default 'unknown',
  add column if not exists dating_confirmed boolean not null default false,
  add column if not exists completed_at timestamptz,
  add column if not exists synthetic boolean not null default true;

alter table public.pregnancies
  add constraint pregnancies_dating_source_check check (
    dating_source in (
      'unknown',
      'user_reported_lmp',
      'clinician_estimated_due_date',
      'ultrasound_estimated_due_date'
    )
  );

alter table public.pregnancies
  add constraint pregnancies_dating_reference_check check (
    (dating_source <> 'user_reported_lmp' or last_menstrual_period is not null)
    and (
      dating_source not in ('clinician_estimated_due_date', 'ultrasound_estimated_due_date')
      or estimated_due_date is not null
    )
    and (not dating_confirmed or dating_source <> 'unknown')
  );

alter table public.attachment_records
  add column if not exists document_date date,
  add column if not exists display_label text,
  add column if not exists capture_source text not null default 'file_upload',
  add column if not exists file_size_bytes bigint,
  add column if not exists content_sha256 text,
  add column if not exists synthetic boolean not null default true;

alter table public.attachment_records
  add constraint attachment_display_label_check check (
    display_label is null or length(display_label) between 1 and 120
  ),
  add constraint attachment_capture_source_check check (
    capture_source in ('camera', 'file_upload', 'scan_import', 'other')
  ),
  add constraint attachment_file_size_check check (
    file_size_bytes is null or file_size_bytes > 0
  ),
  add constraint attachment_content_sha256_check check (
    content_sha256 is null or content_sha256 ~ '^[0-9a-fA-F]{64}$'
  );

create index if not exists attachment_records_user_pregnancy_created_idx
  on public.attachment_records(user_id, pregnancy_id, created_at desc);
create index if not exists attachment_records_user_content_sha_idx
  on public.attachment_records(user_id, content_sha256)
  where content_sha256 is not null;

create table if not exists public.pregnancy_observations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  pregnancy_id uuid not null references public.pregnancies(id) on delete cascade,
  kind text not null check (kind in ('weight', 'blood_pressure', 'lab_result')),
  observed_at timestamptz not null,
  source text not null check (
    source in ('user_entered', 'clinician_entered', 'document_confirmed')
  ),
  confirmed boolean not null default false,
  weight_kg numeric(6,2) check (weight_kg is null or (weight_kg > 20 and weight_kg <= 300)),
  systolic_mm_hg smallint check (
    systolic_mm_hg is null or (systolic_mm_hg > 0 and systolic_mm_hg <= 400)
  ),
  diastolic_mm_hg smallint check (
    diastolic_mm_hg is null or (diastolic_mm_hg > 0 and diastolic_mm_hg <= 400)
  ),
  label text check (label is null or length(label) between 1 and 120),
  value_text text check (value_text is null or length(value_text) between 1 and 200),
  unit text check (unit is null or length(unit) <= 60),
  source_attachment_id uuid references public.attachment_records(id) on delete restrict,
  supersedes_observation_id uuid references public.pregnancy_observations(id) on delete restrict,
  synthetic boolean not null default true,
  created_at timestamptz not null default now(),
  constraint pregnancy_observation_shape_check check (
    (kind <> 'weight' or weight_kg is not null)
    and (
      kind <> 'blood_pressure'
      or (systolic_mm_hg is not null and diastolic_mm_hg is not null)
    )
    and (kind <> 'lab_result' or (label is not null and value_text is not null))
  ),
  constraint pregnancy_observation_document_source_check check (
    source <> 'document_confirmed'
    or (confirmed and source_attachment_id is not null)
  ),
  constraint pregnancy_observation_not_self_superseding check (
    supersedes_observation_id is null or supersedes_observation_id <> id
  )
);

create index if not exists pregnancy_observations_user_pregnancy_time_idx
  on public.pregnancy_observations(user_id, pregnancy_id, observed_at desc);

create table if not exists public.pregnancy_encounters (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  pregnancy_id uuid not null references public.pregnancies(id) on delete cascade,
  occurred_at timestamptz not null,
  encounter_type text not null check (
    encounter_type in ('routine_visit', 'scan', 'lab_review', 'procedure', 'other')
  ),
  summary text check (summary is null or length(summary) <= 2000),
  next_follow_up_at timestamptz,
  source text not null check (
    source in ('user_entered', 'clinician_entered', 'document_confirmed')
  ),
  confirmed boolean not null default false,
  source_attachment_id uuid references public.attachment_records(id) on delete restrict,
  supersedes_encounter_id uuid references public.pregnancy_encounters(id) on delete restrict,
  synthetic boolean not null default true,
  created_at timestamptz not null default now(),
  constraint pregnancy_encounter_follow_up_check check (
    next_follow_up_at is null or next_follow_up_at >= occurred_at
  ),
  constraint pregnancy_encounter_document_source_check check (
    source <> 'document_confirmed'
    or (confirmed and source_attachment_id is not null)
  ),
  constraint pregnancy_encounter_not_self_superseding check (
    supersedes_encounter_id is null or supersedes_encounter_id <> id
  )
);

create index if not exists pregnancy_encounters_user_pregnancy_time_idx
  on public.pregnancy_encounters(user_id, pregnancy_id, occurred_at desc);

create or replace function public.enforce_janani_observation_links()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1
    from public.pregnancies pregnancy
    where pregnancy.id = new.pregnancy_id
      and pregnancy.user_id = new.user_id
  ) then
    raise exception 'pregnancy_id does not belong to record owner'
      using errcode = '42501';
  end if;

  if new.source_attachment_id is not null and not exists (
    select 1
    from public.attachment_records attachment
    where attachment.id = new.source_attachment_id
      and attachment.user_id = new.user_id
      and attachment.pregnancy_id = new.pregnancy_id
  ) then
    raise exception 'source attachment does not belong to pregnancy owner'
      using errcode = '42501';
  end if;

  if new.supersedes_observation_id is not null and not exists (
    select 1
    from public.pregnancy_observations previous
    where previous.id = new.supersedes_observation_id
      and previous.user_id = new.user_id
      and previous.pregnancy_id = new.pregnancy_id
  ) then
    raise exception 'superseded observation does not belong to pregnancy owner'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

create trigger enforce_pregnancy_observation_links
before insert on public.pregnancy_observations
for each row execute function public.enforce_janani_observation_links();

create or replace function public.enforce_janani_encounter_links()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1
    from public.pregnancies pregnancy
    where pregnancy.id = new.pregnancy_id
      and pregnancy.user_id = new.user_id
  ) then
    raise exception 'pregnancy_id does not belong to record owner'
      using errcode = '42501';
  end if;

  if new.source_attachment_id is not null and not exists (
    select 1
    from public.attachment_records attachment
    where attachment.id = new.source_attachment_id
      and attachment.user_id = new.user_id
      and attachment.pregnancy_id = new.pregnancy_id
  ) then
    raise exception 'source attachment does not belong to pregnancy owner'
      using errcode = '42501';
  end if;

  if new.supersedes_encounter_id is not null and not exists (
    select 1
    from public.pregnancy_encounters previous
    where previous.id = new.supersedes_encounter_id
      and previous.user_id = new.user_id
      and previous.pregnancy_id = new.pregnancy_id
  ) then
    raise exception 'superseded encounter does not belong to pregnancy owner'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

create trigger enforce_pregnancy_encounter_links
before insert on public.pregnancy_encounters
for each row execute function public.enforce_janani_encounter_links();

alter table public.pregnancy_observations enable row level security;
alter table public.pregnancy_encounters enable row level security;

create policy pregnancy_observations_select_own
on public.pregnancy_observations for select
to authenticated
using ((select auth.uid()) = user_id);

create policy pregnancy_observations_insert_own
on public.pregnancy_observations for insert
to authenticated
with check (
  (select auth.uid()) = user_id
  and exists (
    select 1 from public.pregnancies pregnancy
    where pregnancy.id = pregnancy_id
      and pregnancy.user_id = (select auth.uid())
  )
);

create policy pregnancy_encounters_select_own
on public.pregnancy_encounters for select
to authenticated
using ((select auth.uid()) = user_id);

create policy pregnancy_encounters_insert_own
on public.pregnancy_encounters for insert
to authenticated
with check (
  (select auth.uid()) = user_id
  and exists (
    select 1 from public.pregnancies pregnancy
    where pregnancy.id = pregnancy_id
      and pregnancy.user_id = (select auth.uid())
  )
);

revoke all on public.pregnancy_observations from anon, authenticated;
revoke all on public.pregnancy_encounters from anon, authenticated;
grant select, insert on public.pregnancy_observations to authenticated;
grant select, insert on public.pregnancy_encounters to authenticated;
grant all on public.pregnancy_observations to service_role;
grant all on public.pregnancy_encounters to service_role;

comment on table public.pregnancy_observations is
  'Append-only structured measurements and lab-result facts. Values are stored without interpretation.';
comment on table public.pregnancy_encounters is
  'Append-only pregnancy encounter timeline. Corrections are represented by superseding records.';
comment on column public.attachment_records.content_sha256 is
  'Optional file-content digest for integrity/deduplication; never an authentication credential.';
