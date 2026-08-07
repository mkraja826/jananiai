-- Janani AI Phase 10: deterministic reminder delivery queue and neutral response events.
-- Delivery rows contain IDs, timing, status, and retry metadata only. They intentionally
-- exclude medication names, clinical text, symptoms, reports, prompts, and model output.

create table if not exists public.reminder_delivery_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  reminder_kind text not null check (reminder_kind in ('medication', 'appointment')),
  medication_reminder_id uuid references public.medication_reminder_schedules(id) on delete cascade,
  appointment_reminder_id uuid references public.appointment_reminder_schedules(id) on delete cascade,
  scheduled_for timestamptz not null,
  next_attempt_at timestamptz not null,
  origin text not null default 'schedule' check (origin in ('schedule', 'remind_later')),
  status text not null default 'pending' check (
    status in ('pending', 'claimed', 'sent', 'failed', 'cancelled')
  ),
  attempt_count smallint not null default 0 check (attempt_count between 0 and 5),
  claim_token uuid,
  claimed_at timestamptz,
  completed_at timestamptz,
  failure_code text check (failure_code is null or length(failure_code) between 1 and 100),
  synthetic boolean not null default true,
  created_at timestamptz not null default now(),
  constraint reminder_delivery_exact_schedule_reference check (
    (
      reminder_kind = 'medication'
      and medication_reminder_id is not null
      and appointment_reminder_id is null
    )
    or (
      reminder_kind = 'appointment'
      and appointment_reminder_id is not null
      and medication_reminder_id is null
    )
  ),
  constraint reminder_delivery_state_check check (
    (
      status = 'pending'
      and claim_token is null
      and claimed_at is null
      and completed_at is null
      and failure_code is null
    )
    or (
      status = 'claimed'
      and claim_token is not null
      and claimed_at is not null
      and completed_at is null
      and failure_code is null
    )
    or (
      status in ('sent', 'failed', 'cancelled')
      and completed_at is not null
    )
  )
);

create unique index if not exists reminder_delivery_medication_occurrence_unique_idx
  on public.reminder_delivery_jobs(medication_reminder_id, scheduled_for)
  where medication_reminder_id is not null;
create unique index if not exists reminder_delivery_appointment_occurrence_unique_idx
  on public.reminder_delivery_jobs(appointment_reminder_id, scheduled_for)
  where appointment_reminder_id is not null;
create index if not exists reminder_delivery_due_idx
  on public.reminder_delivery_jobs(next_attempt_at, scheduled_for)
  where status = 'pending';
create index if not exists reminder_delivery_user_time_idx
  on public.reminder_delivery_jobs(user_id, scheduled_for desc);

create table if not exists public.reminder_response_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  delivery_id uuid not null references public.reminder_delivery_jobs(id) on delete cascade,
  client_event_id uuid not null,
  event_type text not null check (
    event_type in ('opened', 'acknowledged', 'dismissed', 'remind_later')
  ),
  occurred_at timestamptz not null,
  remind_at timestamptz,
  synthetic boolean not null default true,
  created_at timestamptz not null default now(),
  constraint reminder_response_remind_later_check check (
    (
      event_type = 'remind_later'
      and remind_at is not null
      and remind_at > occurred_at
    )
    or (
      event_type <> 'remind_later'
      and remind_at is null
    )
  ),
  constraint reminder_response_idempotency_unique unique (user_id, client_event_id)
);

create index if not exists reminder_response_user_time_idx
  on public.reminder_response_events(user_id, occurred_at desc);
create index if not exists reminder_response_delivery_idx
  on public.reminder_response_events(delivery_id, occurred_at desc);

alter table public.reminder_delivery_jobs enable row level security;
alter table public.reminder_response_events enable row level security;

create policy reminder_delivery_jobs_select_own
on public.reminder_delivery_jobs for select
to authenticated
using ((select auth.uid()) = user_id);

create policy reminder_response_events_select_own
on public.reminder_response_events for select
to authenticated
using ((select auth.uid()) = user_id);

revoke all on public.reminder_delivery_jobs from anon, authenticated;
revoke all on public.reminder_response_events from anon, authenticated;
grant select on public.reminder_delivery_jobs to authenticated;
grant select on public.reminder_response_events to authenticated;
grant all on public.reminder_delivery_jobs to service_role;
grant all on public.reminder_response_events to service_role;

create or replace function public.materialize_janani_reminder_deliveries(
  p_window_start timestamptz,
  p_window_end timestamptz
)
returns integer
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_inserted integer := 0;
  v_total integer := 0;
begin
  if p_window_start is null
    or p_window_end is null
    or p_window_end <= p_window_start
    or p_window_end - p_window_start > interval '8 days'
  then
    raise exception 'Materialization window must be positive and no longer than 8 days'
      using errcode = '22023';
  end if;

  insert into public.reminder_delivery_jobs (
    user_id,
    reminder_kind,
    medication_reminder_id,
    scheduled_for,
    next_attempt_at,
    origin,
    synthetic
  )
  select
    schedule.user_id,
    'medication',
    schedule.id,
    occurrence.scheduled_for,
    occurrence.scheduled_for,
    'schedule',
    schedule.synthetic
  from public.medication_reminder_schedules schedule
  join public.medication_records medication
    on medication.id = schedule.medication_id
   and medication.user_id = schedule.user_id
  cross join lateral generate_series(
    ((p_window_start at time zone schedule.timezone_name)::date - 1)::timestamp,
    ((p_window_end at time zone schedule.timezone_name)::date + 1)::timestamp,
    interval '1 day'
  ) as local_day(value)
  cross join lateral (
    select ((local_day.value::date + schedule.local_time) at time zone schedule.timezone_name)
      as scheduled_for
  ) occurrence
  where schedule.enabled
    and medication.active
    and medication.confirmed
    and local_day.value::date >= schedule.start_date
    and (schedule.end_date is null or local_day.value::date <= schedule.end_date)
    and extract(isodow from local_day.value)::smallint = any(schedule.weekdays)
    and occurrence.scheduled_for >= p_window_start
    and occurrence.scheduled_for < p_window_end
  on conflict do nothing;

  get diagnostics v_inserted = row_count;
  v_total := v_total + v_inserted;

  insert into public.reminder_delivery_jobs (
    user_id,
    reminder_kind,
    appointment_reminder_id,
    scheduled_for,
    next_attempt_at,
    origin,
    synthetic
  )
  select
    schedule.user_id,
    'appointment',
    schedule.id,
    appointment.scheduled_at - make_interval(mins => schedule.lead_minutes),
    appointment.scheduled_at - make_interval(mins => schedule.lead_minutes),
    'schedule',
    schedule.synthetic
  from public.appointment_reminder_schedules schedule
  join public.appointment_records appointment
    on appointment.id = schedule.appointment_id
   and appointment.user_id = schedule.user_id
  where schedule.enabled
    and appointment.status = 'scheduled'
    and appointment.scheduled_at - make_interval(mins => schedule.lead_minutes) >= p_window_start
    and appointment.scheduled_at - make_interval(mins => schedule.lead_minutes) < p_window_end
  on conflict do nothing;

  get diagnostics v_inserted = row_count;
  v_total := v_total + v_inserted;
  return v_total;
end;
$$;

create or replace function public.claim_janani_reminder_deliveries(
  p_now timestamptz,
  p_limit integer default 50
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_result jsonb;
begin
  if p_now is null or p_limit is null or p_limit < 1 or p_limit > 100 then
    raise exception 'Invalid reminder delivery claim request' using errcode = '22023';
  end if;

  update public.reminder_delivery_jobs
  set
    status = 'failed',
    completed_at = p_now,
    failure_code = 'claim_timeout_max_attempts'
  where status = 'claimed'
    and claimed_at < p_now - interval '15 minutes'
    and attempt_count >= 5;

  update public.reminder_delivery_jobs
  set
    status = 'pending',
    claim_token = null,
    claimed_at = null,
    next_attempt_at = p_now + make_interval(mins => least(attempt_count * 5, 30))
  where status = 'claimed'
    and claimed_at < p_now - interval '15 minutes'
    and attempt_count < 5;

  with picked as (
    select job.id
    from public.reminder_delivery_jobs job
    where job.status = 'pending'
      and job.scheduled_for <= p_now
      and job.next_attempt_at <= p_now
    order by job.scheduled_for, job.id
    for update skip locked
    limit p_limit
  ), claimed as (
    update public.reminder_delivery_jobs job
    set
      status = 'claimed',
      claim_token = gen_random_uuid(),
      claimed_at = p_now,
      attempt_count = job.attempt_count + 1
    from picked
    where job.id = picked.id
    returning job.*
  )
  select coalesce(jsonb_agg(to_jsonb(claimed) order by claimed.scheduled_for), '[]'::jsonb)
  into v_result
  from claimed;

  return v_result;
end;
$$;

create or replace function public.complete_janani_reminder_delivery(
  p_delivery_id uuid,
  p_claim_token uuid,
  p_outcome text,
  p_failure_code text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_job public.reminder_delivery_jobs%rowtype;
  v_failure_code text;
begin
  if p_outcome not in ('sent', 'retryable_failure', 'terminal_failure') then
    raise exception 'Unsupported reminder dispatch outcome' using errcode = '22023';
  end if;
  if p_failure_code is not null and (length(p_failure_code) < 1 or length(p_failure_code) > 100) then
    raise exception 'failure_code must contain 1 to 100 characters' using errcode = '22023';
  end if;

  select *
  into v_job
  from public.reminder_delivery_jobs job
  where job.id = p_delivery_id
    and job.status = 'claimed'
    and job.claim_token = p_claim_token
  for update;

  if not found then
    raise exception 'Reminder delivery claim is stale or invalid' using errcode = '22023';
  end if;

  if p_outcome = 'sent' then
    update public.reminder_delivery_jobs
    set
      status = 'sent',
      completed_at = now(),
      failure_code = null
    where id = p_delivery_id
    returning * into v_job;
  elsif p_outcome = 'retryable_failure' and v_job.attempt_count < 5 then
    update public.reminder_delivery_jobs
    set
      status = 'pending',
      claim_token = null,
      claimed_at = null,
      completed_at = null,
      failure_code = null,
      next_attempt_at = now() + make_interval(mins => least(v_job.attempt_count * 5, 30))
    where id = p_delivery_id
    returning * into v_job;
  else
    v_failure_code := coalesce(p_failure_code, 'dispatch_failed');
    update public.reminder_delivery_jobs
    set
      status = 'failed',
      completed_at = now(),
      failure_code = v_failure_code
    where id = p_delivery_id
    returning * into v_job;
  end if;

  return to_jsonb(v_job);
end;
$$;

create or replace function public.record_janani_reminder_response(
  p_client_event_id uuid,
  p_delivery_id uuid,
  p_event_type text,
  p_occurred_at timestamptz,
  p_remind_at timestamptz,
  p_synthetic boolean
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_user_id uuid := auth.uid();
  v_delivery public.reminder_delivery_jobs%rowtype;
  v_existing public.reminder_response_events%rowtype;
  v_event public.reminder_response_events%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if p_client_event_id is null or p_occurred_at is null then
    raise exception 'Response identity and occurrence time are required' using errcode = '22023';
  end if;
  if p_event_type not in ('opened', 'acknowledged', 'dismissed', 'remind_later') then
    raise exception 'Unsupported reminder response type' using errcode = '22023';
  end if;
  if p_event_type = 'remind_later' then
    if p_remind_at is null or p_remind_at <= p_occurred_at then
      raise exception 'remind_later requires an explicit future remind_at time'
        using errcode = '22023';
    end if;
  elsif p_remind_at is not null then
    raise exception 'remind_at is allowed only for remind_later events' using errcode = '22023';
  end if;

  select *
  into v_delivery
  from public.reminder_delivery_jobs job
  where job.id = p_delivery_id
    and job.user_id = v_user_id;

  if not found then
    raise exception 'Reminder delivery not found' using errcode = '42501';
  end if;
  if v_delivery.status <> 'sent' then
    raise exception 'Only sent reminder deliveries can receive user responses'
      using errcode = '22023';
  end if;

  select *
  into v_existing
  from public.reminder_response_events response
  where response.user_id = v_user_id
    and response.client_event_id = p_client_event_id;

  if found then
    if v_existing.delivery_id <> p_delivery_id
      or v_existing.event_type <> p_event_type
      or v_existing.occurred_at <> p_occurred_at
      or v_existing.remind_at is distinct from p_remind_at
      or v_existing.synthetic <> coalesce(p_synthetic, true)
    then
      raise exception 'client_event_id was already used for a different response'
        using errcode = '22023';
    end if;
    return to_jsonb(v_existing);
  end if;

  insert into public.reminder_response_events (
    user_id,
    delivery_id,
    client_event_id,
    event_type,
    occurred_at,
    remind_at,
    synthetic
  )
  values (
    v_user_id,
    p_delivery_id,
    p_client_event_id,
    p_event_type,
    p_occurred_at,
    p_remind_at,
    coalesce(p_synthetic, true)
  )
  returning * into v_event;

  if p_event_type = 'remind_later' then
    insert into public.reminder_delivery_jobs (
      user_id,
      reminder_kind,
      medication_reminder_id,
      appointment_reminder_id,
      scheduled_for,
      next_attempt_at,
      origin,
      synthetic
    )
    values (
      v_user_id,
      v_delivery.reminder_kind,
      v_delivery.medication_reminder_id,
      v_delivery.appointment_reminder_id,
      p_remind_at,
      p_remind_at,
      'remind_later',
      v_delivery.synthetic
    )
    on conflict do nothing;
  end if;

  return to_jsonb(v_event);
end;
$$;

create or replace function public.cancel_janani_delivery_jobs_for_disabled_schedule()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if old.enabled and not new.enabled then
    if tg_table_name = 'medication_reminder_schedules' then
      update public.reminder_delivery_jobs
      set status = 'cancelled', completed_at = now()
      where medication_reminder_id = new.id
        and status in ('pending', 'claimed');
    elsif tg_table_name = 'appointment_reminder_schedules' then
      update public.reminder_delivery_jobs
      set status = 'cancelled', completed_at = now()
      where appointment_reminder_id = new.id
        and status in ('pending', 'claimed');
    end if;
  end if;
  return new;
end;
$$;

create trigger cancel_delivery_jobs_when_medication_reminder_disabled
after update of enabled on public.medication_reminder_schedules
for each row execute function public.cancel_janani_delivery_jobs_for_disabled_schedule();

create trigger cancel_delivery_jobs_when_appointment_reminder_disabled
after update of enabled on public.appointment_reminder_schedules
for each row execute function public.cancel_janani_delivery_jobs_for_disabled_schedule();

create or replace function public.cancel_janani_delivery_jobs_for_source_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_table_name = 'medication_records' then
    if (old.active and not new.active) or (old.confirmed and not new.confirmed) then
      update public.reminder_delivery_jobs job
      set status = 'cancelled', completed_at = now()
      where job.medication_reminder_id in (
        select schedule.id
        from public.medication_reminder_schedules schedule
        where schedule.medication_id = new.id
      )
        and job.status in ('pending', 'claimed');
    end if;
  elsif tg_table_name = 'appointment_records' then
    if old.status = 'scheduled' and new.status <> 'scheduled' then
      update public.reminder_delivery_jobs job
      set status = 'cancelled', completed_at = now()
      where job.appointment_reminder_id in (
        select schedule.id
        from public.appointment_reminder_schedules schedule
        where schedule.appointment_id = new.id
      )
        and job.status in ('pending', 'claimed');
    end if;
  end if;
  return new;
end;
$$;

create trigger cancel_delivery_jobs_when_medication_state_changes
after update of active, confirmed on public.medication_records
for each row execute function public.cancel_janani_delivery_jobs_for_source_change();

create trigger cancel_delivery_jobs_when_appointment_state_changes
after update of status on public.appointment_records
for each row execute function public.cancel_janani_delivery_jobs_for_source_change();

revoke all on function public.materialize_janani_reminder_deliveries(timestamptz, timestamptz)
  from public, anon, authenticated;
revoke all on function public.claim_janani_reminder_deliveries(timestamptz, integer)
  from public, anon, authenticated;
revoke all on function public.complete_janani_reminder_delivery(uuid, uuid, text, text)
  from public, anon, authenticated;
revoke all on function public.record_janani_reminder_response(uuid, uuid, text, timestamptz, timestamptz, boolean)
  from public, anon;

grant execute on function public.materialize_janani_reminder_deliveries(timestamptz, timestamptz)
  to service_role;
grant execute on function public.claim_janani_reminder_deliveries(timestamptz, integer)
  to service_role;
grant execute on function public.complete_janani_reminder_delivery(uuid, uuid, text, text)
  to service_role;
grant execute on function public.record_janani_reminder_response(uuid, uuid, text, timestamptz, timestamptz, boolean)
  to authenticated;

comment on table public.reminder_delivery_jobs is
  'Privacy-minimised reminder delivery queue. Contains opaque references and timing/status metadata only; no clinical message text.';
comment on table public.reminder_response_events is
  'Append-only neutral user interactions with sent reminder deliveries. No medication adherence or dose-taking inference is recorded.';
comment on function public.materialize_janani_reminder_deliveries(timestamptz, timestamptz) is
  'Service-only deterministic materialization from explicit schedules using PostgreSQL timezone data.';
comment on function public.claim_janani_reminder_deliveries(timestamptz, integer) is
  'Service-only bounded queue claim with stale-claim recovery and retry backoff.';
