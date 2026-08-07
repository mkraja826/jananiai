-- Keep claim, retry, and completion timestamps on one explicit worker clock.

drop function if exists public.complete_janani_reminder_delivery(uuid, uuid, text, text);

create or replace function public.complete_janani_reminder_delivery(
  p_delivery_id uuid,
  p_claim_token uuid,
  p_outcome text,
  p_now timestamptz,
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
  if p_now is null then
    raise exception 'Completion time is required' using errcode = '22023';
  end if;
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
      completed_at = p_now,
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
      next_attempt_at = p_now + make_interval(mins => least(v_job.attempt_count * 5, 30))
    where id = p_delivery_id
    returning * into v_job;
  else
    v_failure_code := coalesce(p_failure_code, 'dispatch_failed');
    update public.reminder_delivery_jobs
    set
      status = 'failed',
      completed_at = p_now,
      failure_code = v_failure_code
    where id = p_delivery_id
    returning * into v_job;
  end if;

  return to_jsonb(v_job);
end;
$$;

revoke all on function public.complete_janani_reminder_delivery(uuid, uuid, text, timestamptz, text)
  from public, anon, authenticated;
grant execute on function public.complete_janani_reminder_delivery(uuid, uuid, text, timestamptz, text)
  to service_role;
