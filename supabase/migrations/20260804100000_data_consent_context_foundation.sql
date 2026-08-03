-- Janani AI Phase 2: user-owned health records, append-only consent,
-- private attachment metadata, and privacy-minimised context assembly audits.

create extension if not exists pgcrypto;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'janani_consent_purpose') then
    create type public.janani_consent_purpose as enum (
      'care_support',
      'ai_processing',
      'attachment_processing',
      'model_improvement',
      'research'
    );
  end if;

  if not exists (select 1 from pg_type where typname = 'janani_consent_status') then
    create type public.janani_consent_status as enum ('granted', 'revoked');
  end if;

  if not exists (select 1 from pg_type where typname = 'janani_attachment_kind') then
    create type public.janani_attachment_kind as enum (
      'lab_report',
      'ultrasound_report',
      'prescription',
      'discharge_summary',
      'other_document'
    );
  end if;

  if not exists (select 1 from pg_type where typname = 'janani_extraction_status') then
    create type public.janani_extraction_status as enum (
      'not_started',
      'processing',
      'completed',
      'failed'
    );
  end if;

  if not exists (select 1 from pg_type where typname = 'janani_confirmation_status') then
    create type public.janani_confirmation_status as enum (
      'unconfirmed',
      'confirmed',
      'rejected'
    );
  end if;
end
$$;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.user_health_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  preferred_language text not null default 'en' check (preferred_language in ('en', 'te')),
  dietary_preference text not null default 'not_specified',
  height_cm numeric(5,2) check (height_cm is null or (height_cm > 100 and height_cm <= 220)),
  allergies text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.pregnancies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  gestational_week smallint not null check (gestational_week between 0 and 45),
  estimated_due_date date,
  known_conditions text[] not null default '{}',
  weight_kg numeric(6,2) check (weight_kg is null or (weight_kg > 20 and weight_kg <= 300)),
  clinician_restrictions text[] not null default '{}',
  status text not null default 'active' check (status in ('active', 'completed', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists pregnancies_user_id_idx on public.pregnancies(user_id);

create table if not exists public.consent_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  purpose public.janani_consent_purpose not null,
  status public.janani_consent_status not null,
  policy_version text not null check (length(policy_version) between 1 and 50),
  source text not null default 'mobile_app',
  occurred_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists consent_events_user_purpose_time_idx
  on public.consent_events(user_id, purpose, occurred_at desc);

create table if not exists public.medication_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  pregnancy_id uuid references public.pregnancies(id) on delete cascade,
  name text not null check (length(name) between 1 and 200),
  dose_text text check (dose_text is null or length(dose_text) <= 200),
  schedule_text text check (schedule_text is null or length(schedule_text) <= 300),
  source text not null check (
    source in ('user_entered', 'clinician_entered', 'prescription_confirmed')
  ),
  confirmed boolean not null default false,
  active boolean not null default true,
  recorded_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint prescription_confirmed_requires_confirmation check (
    source <> 'prescription_confirmed' or confirmed
  )
);

create index if not exists medication_records_user_id_idx
  on public.medication_records(user_id, recorded_at desc);

create table if not exists public.appointment_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  pregnancy_id uuid references public.pregnancies(id) on delete cascade,
  scheduled_at timestamptz not null,
  purpose text check (purpose is null or length(purpose) <= 300),
  status text not null default 'scheduled' check (
    status in ('scheduled', 'completed', 'cancelled')
  ),
  notes text check (notes is null or length(notes) <= 1000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists appointment_records_user_id_idx
  on public.appointment_records(user_id, scheduled_at desc);

create table if not exists public.attachment_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  pregnancy_id uuid references public.pregnancies(id) on delete cascade,
  kind public.janani_attachment_kind not null,
  mime_type text not null check (length(mime_type) between 1 and 150),
  storage_object_path text not null unique,
  extraction_status public.janani_extraction_status not null default 'not_started',
  confirmation_status public.janani_confirmation_status not null default 'unconfirmed',
  latest_extraction_confidence numeric(5,4) check (
    latest_extraction_confidence is null
    or latest_extraction_confidence between 0 and 1
  ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint attachment_path_starts_with_owner check (
    storage_object_path like user_id::text || '/%'
  )
);

create index if not exists attachment_records_user_id_idx
  on public.attachment_records(user_id, created_at desc);

create table if not exists public.attachment_extractions (
  id uuid primary key default gen_random_uuid(),
  attachment_id uuid not null references public.attachment_records(id) on delete cascade,
  extractor_name text not null,
  extractor_version text not null,
  extracted_text text not null check (length(extracted_text) between 1 and 20000),
  confidence numeric(5,4) check (confidence is null or confidence between 0 and 1),
  user_confirmed_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists attachment_extractions_attachment_id_idx
  on public.attachment_extractions(attachment_id, created_at desc);

create table if not exists public.context_assembly_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  task text not null,
  status text not null,
  safety_event_id uuid,
  selected_medication_ids uuid[] not null default '{}',
  selected_appointment_ids uuid[] not null default '{}',
  selected_attachment_ids uuid[] not null default '{}',
  selected_knowledge_ids text[] not null default '{}',
  excluded_item_count integer not null default 0 check (excluded_item_count >= 0),
  schema_version text not null default '1.0',
  synthetic boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists context_assembly_events_user_id_idx
  on public.context_assembly_events(user_id, created_at desc);

create trigger set_user_health_profiles_updated_at
before update on public.user_health_profiles
for each row execute function public.set_updated_at();

create trigger set_pregnancies_updated_at
before update on public.pregnancies
for each row execute function public.set_updated_at();

create trigger set_medication_records_updated_at
before update on public.medication_records
for each row execute function public.set_updated_at();

create trigger set_appointment_records_updated_at
before update on public.appointment_records
for each row execute function public.set_updated_at();

create trigger set_attachment_records_updated_at
before update on public.attachment_records
for each row execute function public.set_updated_at();

alter table public.user_health_profiles enable row level security;
alter table public.pregnancies enable row level security;
alter table public.consent_events enable row level security;
alter table public.medication_records enable row level security;
alter table public.appointment_records enable row level security;
alter table public.attachment_records enable row level security;
alter table public.attachment_extractions enable row level security;
alter table public.context_assembly_events enable row level security;

create policy user_health_profiles_select_own
on public.user_health_profiles for select
using (auth.uid() = user_id);

create policy user_health_profiles_insert_own
on public.user_health_profiles for insert
with check (auth.uid() = user_id);

create policy user_health_profiles_update_own
on public.user_health_profiles for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy user_health_profiles_delete_own
on public.user_health_profiles for delete
using (auth.uid() = user_id);

create policy pregnancies_select_own
on public.pregnancies for select
using (auth.uid() = user_id);

create policy pregnancies_insert_own
on public.pregnancies for insert
with check (auth.uid() = user_id);

create policy pregnancies_update_own
on public.pregnancies for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy pregnancies_delete_own
on public.pregnancies for delete
using (auth.uid() = user_id);

create policy consent_events_select_own
on public.consent_events for select
using (auth.uid() = user_id);

create policy consent_events_insert_own
on public.consent_events for insert
with check (auth.uid() = user_id);

create policy medication_records_select_own
on public.medication_records for select
using (auth.uid() = user_id);

create policy medication_records_insert_own
on public.medication_records for insert
with check (
  auth.uid() = user_id
  and (
    pregnancy_id is null
    or exists (
      select 1 from public.pregnancies p
      where p.id = pregnancy_id and p.user_id = auth.uid()
    )
  )
);

create policy medication_records_update_own
on public.medication_records for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy medication_records_delete_own
on public.medication_records for delete
using (auth.uid() = user_id);

create policy appointment_records_select_own
on public.appointment_records for select
using (auth.uid() = user_id);

create policy appointment_records_insert_own
on public.appointment_records for insert
with check (
  auth.uid() = user_id
  and (
    pregnancy_id is null
    or exists (
      select 1 from public.pregnancies p
      where p.id = pregnancy_id and p.user_id = auth.uid()
    )
  )
);

create policy appointment_records_update_own
on public.appointment_records for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy appointment_records_delete_own
on public.appointment_records for delete
using (auth.uid() = user_id);

create policy attachment_records_select_own
on public.attachment_records for select
using (auth.uid() = user_id);

create policy attachment_records_insert_own
on public.attachment_records for insert
with check (
  auth.uid() = user_id
  and storage_object_path like auth.uid()::text || '/%'
  and (
    pregnancy_id is null
    or exists (
      select 1 from public.pregnancies p
      where p.id = pregnancy_id and p.user_id = auth.uid()
    )
  )
);

create policy attachment_records_update_own
on public.attachment_records for update
using (auth.uid() = user_id)
with check (
  auth.uid() = user_id
  and storage_object_path like auth.uid()::text || '/%'
);

create policy attachment_records_delete_own
on public.attachment_records for delete
using (auth.uid() = user_id);

create policy attachment_extractions_select_owned
on public.attachment_extractions for select
using (
  exists (
    select 1 from public.attachment_records attachment
    where attachment.id = attachment_id and attachment.user_id = auth.uid()
  )
);

create policy context_assembly_events_select_own
on public.context_assembly_events for select
using (auth.uid() = user_id);

revoke all on public.attachment_extractions from anon, authenticated;
revoke all on public.context_assembly_events from anon, authenticated;
grant select on public.attachment_extractions to authenticated;
grant select on public.context_assembly_events to authenticated;

insert into storage.buckets (id, name, public)
values ('janani-private', 'janani-private', false)
on conflict (id) do update set public = false;

create policy janani_private_storage_select_own
on storage.objects for select
to authenticated
using (
  bucket_id = 'janani-private'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy janani_private_storage_insert_own
on storage.objects for insert
to authenticated
with check (
  bucket_id = 'janani-private'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy janani_private_storage_update_own
on storage.objects for update
to authenticated
using (
  bucket_id = 'janani-private'
  and (storage.foldername(name))[1] = auth.uid()::text
)
with check (
  bucket_id = 'janani-private'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy janani_private_storage_delete_own
on storage.objects for delete
to authenticated
using (
  bucket_id = 'janani-private'
  and (storage.foldername(name))[1] = auth.uid()::text
);

comment on table public.consent_events is
  'Append-only consent history. Revocation is represented by a new event, never an update.';
comment on table public.attachment_extractions is
  'Backend-written extraction versions. Users may read only extractions for owned attachments.';
comment on table public.context_assembly_events is
  'Privacy-minimised backend audit events; raw questions, prompts, reports, and model outputs are excluded.';
