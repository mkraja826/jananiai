-- Janani AI Phase 11: private notification-device lifecycle and claim-bound destination lookup.
-- Raw push tokens are backend-only secrets. User-facing APIs return metadata only.

create table if not exists public.notification_devices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  installation_id uuid not null,
  platform text not null check (platform in ('android', 'ios', 'web')),
  transport text not null check (transport in ('mock')),
  push_token text not null check (length(btrim(push_token)) between 8 and 4096),
  token_fingerprint text not null check (token_fingerprint ~ '^[0-9a-f]{64}$'),
  active boolean not null default true,
  synthetic boolean not null default true,
  registered_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  revoked_at timestamptz,
  constraint notification_device_installation_unique unique (user_id, installation_id),
  constraint notification_device_active_state check (
    (active and revoked_at is null)
    or (not active and revoked_at is not null)
  )
);

create index if not exists notification_devices_user_active_idx
  on public.notification_devices(user_id, active, updated_at desc);
create index if not exists notification_devices_token_fingerprint_idx
  on public.notification_devices(transport, token_fingerprint)
  where active;

alter table public.notification_devices enable row level security;

revoke all on public.notification_devices from public, anon, authenticated;
grant all on public.notification_devices to service_role;

create or replace function public.register_janani_notification_device(
  p_installation_id uuid,
  p_platform text,
  p_transport text,
  p_push_token text,
  p_synthetic boolean
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_catalog
as $$
declare
  v_user_id uuid := auth.uid();
  v_token text;
  v_fingerprint text;
  v_device public.notification_devices%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if p_installation_id is null then
    raise exception 'installation_id is required' using errcode = '22023';
  end if;
  if p_platform not in ('android', 'ios', 'web') then
    raise exception 'Unsupported notification platform' using errcode = '22023';
  end if;
  if p_transport <> 'mock' then
    raise exception 'Unsupported notification transport' using errcode = '22023';
  end if;

  v_token := btrim(coalesce(p_push_token, ''));
  if length(v_token) < 8 or length(v_token) > 4096 then
    raise exception 'Invalid push token length' using errcode = '22023';
  end if;
  v_fingerprint := encode(digest(convert_to(v_token, 'UTF8'), 'sha256'), 'hex');

  -- Serialise registrations for the same provider token so two users cannot race
  -- the cross-owner check. The token itself is never placed in the lock key.
  perform pg_advisory_xact_lock(hashtextextended(p_transport || ':' || v_fingerprint, 0));

  if exists (
    select 1
    from public.notification_devices device
    where device.transport = p_transport
      and device.token_fingerprint = v_fingerprint
      and device.user_id <> v_user_id
      and device.active
  ) then
    raise exception 'Notification device registration conflicts with an active registration'
      using errcode = '23505';
  end if;

  insert into public.notification_devices (
    user_id,
    installation_id,
    platform,
    transport,
    push_token,
    token_fingerprint,
    active,
    synthetic,
    registered_at,
    updated_at,
    revoked_at
  )
  values (
    v_user_id,
    p_installation_id,
    p_platform,
    p_transport,
    v_token,
    v_fingerprint,
    true,
    coalesce(p_synthetic, true),
    now(),
    now(),
    null
  )
  on conflict (user_id, installation_id) do update
  set
    platform = excluded.platform,
    transport = excluded.transport,
    push_token = excluded.push_token,
    token_fingerprint = excluded.token_fingerprint,
    active = true,
    synthetic = excluded.synthetic,
    updated_at = now(),
    revoked_at = null
  returning * into v_device;

  return jsonb_build_object(
    'id', v_device.id,
    'installation_id', v_device.installation_id,
    'platform', v_device.platform,
    'transport', v_device.transport,
    'active', v_device.active,
    'synthetic', v_device.synthetic,
    'registered_at', v_device.registered_at,
    'updated_at', v_device.updated_at,
    'revoked_at', v_device.revoked_at
  );
end;
$$;

create or replace function public.list_janani_notification_devices()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_user_id uuid := auth.uid();
  v_result jsonb;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', device.id,
        'installation_id', device.installation_id,
        'platform', device.platform,
        'transport', device.transport,
        'active', device.active,
        'synthetic', device.synthetic,
        'registered_at', device.registered_at,
        'updated_at', device.updated_at,
        'revoked_at', device.revoked_at
      )
      order by device.updated_at desc, device.id
    ),
    '[]'::jsonb
  )
  into v_result
  from public.notification_devices device
  where device.user_id = v_user_id;

  return v_result;
end;
$$;

create or replace function public.revoke_janani_notification_device(
  p_device_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_user_id uuid := auth.uid();
  v_device public.notification_devices%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if p_device_id is null then
    raise exception 'device_id is required' using errcode = '22023';
  end if;

  select *
  into v_device
  from public.notification_devices device
  where device.id = p_device_id
    and device.user_id = v_user_id
  for update;

  if not found then
    raise exception 'Notification device not found' using errcode = '42501';
  end if;

  if v_device.active then
    update public.notification_devices
    set
      active = false,
      revoked_at = now(),
      updated_at = now()
    where id = p_device_id
    returning * into v_device;
  end if;

  return jsonb_build_object(
    'id', v_device.id,
    'installation_id', v_device.installation_id,
    'platform', v_device.platform,
    'transport', v_device.transport,
    'active', v_device.active,
    'synthetic', v_device.synthetic,
    'registered_at', v_device.registered_at,
    'updated_at', v_device.updated_at,
    'revoked_at', v_device.revoked_at
  );
end;
$$;

create or replace function public.get_janani_notification_destinations(
  p_delivery_id uuid,
  p_claim_token uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_job public.reminder_delivery_jobs%rowtype;
  v_result jsonb;
begin
  if p_delivery_id is null or p_claim_token is null then
    raise exception 'Delivery claim identity is required' using errcode = '22023';
  end if;

  select *
  into v_job
  from public.reminder_delivery_jobs job
  where job.id = p_delivery_id
    and job.status = 'claimed'
    and job.claim_token = p_claim_token;

  if not found then
    raise exception 'Reminder delivery claim is stale or invalid' using errcode = '22023';
  end if;

  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', device.id,
        'platform', device.platform,
        'transport', device.transport,
        'push_token', device.push_token,
        'synthetic', device.synthetic
      )
      order by device.updated_at desc, device.id
    ),
    '[]'::jsonb
  )
  into v_result
  from public.notification_devices device
  where device.user_id = v_job.user_id
    and device.active
    and device.synthetic = v_job.synthetic;

  return v_result;
end;
$$;

revoke all on function public.register_janani_notification_device(uuid, text, text, text, boolean)
  from public, anon;
revoke all on function public.list_janani_notification_devices()
  from public, anon;
revoke all on function public.revoke_janani_notification_device(uuid)
  from public, anon;
revoke all on function public.get_janani_notification_destinations(uuid, uuid)
  from public, anon, authenticated;

grant execute on function public.register_janani_notification_device(uuid, text, text, text, boolean)
  to authenticated;
grant execute on function public.list_janani_notification_devices()
  to authenticated;
grant execute on function public.revoke_janani_notification_device(uuid)
  to authenticated;
grant execute on function public.get_janani_notification_destinations(uuid, uuid)
  to service_role;
