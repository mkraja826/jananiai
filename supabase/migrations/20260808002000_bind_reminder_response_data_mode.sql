-- Prevent authenticated callers from relabelling a synthetic reminder interaction as real,
-- or a real delivery interaction as synthetic, when calling the response RPC directly.

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
  if p_client_event_id is null or p_occurred_at is null or p_synthetic is null then
    raise exception 'Response identity, occurrence time, and data mode are required'
      using errcode = '22023';
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
  if p_synthetic is distinct from v_delivery.synthetic then
    raise exception 'Reminder response data mode must match the delivery'
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
      or v_existing.synthetic <> v_delivery.synthetic
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
    v_delivery.synthetic
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

revoke all on function public.record_janani_reminder_response(
  uuid,
  uuid,
  text,
  timestamptz,
  timestamptz,
  boolean
) from public, anon;
grant execute on function public.record_janani_reminder_response(
  uuid,
  uuid,
  text,
  timestamptz,
  timestamptz,
  boolean
) to authenticated;
