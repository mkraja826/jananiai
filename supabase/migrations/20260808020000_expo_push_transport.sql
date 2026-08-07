-- Janani AI Phase 13: guarded Expo Push registration support.
-- Raw tokens remain backend-only and provider delivery remains blocked in production.

alter table public.notification_devices
  drop constraint if exists notification_devices_transport_check;

alter table public.notification_devices
  add constraint notification_devices_transport_check
  check (transport in ('mock', 'expo'));

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
  if p_transport not in ('mock', 'expo') then
    raise exception 'Unsupported notification transport' using errcode = '22023';
  end if;
  if p_transport = 'expo' and p_platform = 'web' then
    raise exception 'Expo push transport supports Android and iOS only' using errcode = '22023';
  end if;

  v_token := btrim(coalesce(p_push_token, ''));
  if length(v_token) < 8 or length(v_token) > 4096 then
    raise exception 'Invalid push token length' using errcode = '22023';
  end if;
  if p_transport = 'expo'
    and v_token !~ '^(Expo|Exponent)PushToken\[[^]]+\]$'
  then
    raise exception 'Invalid Expo push token' using errcode = '22023';
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

revoke all on function public.register_janani_notification_device(uuid, text, text, text, boolean)
  from public, anon;
grant execute on function public.register_janani_notification_device(uuid, text, text, text, boolean)
  to authenticated;
