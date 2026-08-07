from pathlib import Path

MIGRATION = Path("supabase/migrations/20260808010000_notification_devices_transport.sql")


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_raw_device_table_is_private_to_service_role() -> None:
    sql = migration_sql()

    assert "alter table public.notification_devices enable row level security" in sql
    assert "revoke all on public.notification_devices from public, anon, authenticated" in sql
    assert "grant all on public.notification_devices to service_role" in sql
    assert "grant select on public.notification_devices to authenticated" not in sql


def test_user_device_rpcs_derive_identity_and_do_not_accept_user_id() -> None:
    sql = migration_sql()

    for function_name in (
        "register_janani_notification_device",
        "list_janani_notification_devices",
        "revoke_janani_notification_device",
    ):
        assert f"create or replace function public.{function_name}" in sql
    assert "v_user_id uuid := auth.uid()" in sql
    assert (
        "p_user_id"
        not in sql.split(
            "create or replace function public.register_janani_notification_device", 1
        )[1].split("returns jsonb", 1)[0]
    )


def test_worker_destination_lookup_is_claim_bound_and_service_only() -> None:
    sql = migration_sql()

    signature = "public.get_janani_notification_destinations(uuid, uuid)"
    assert "p_delivery_id uuid" in sql
    assert "p_claim_token uuid" in sql
    assert "job.status = 'claimed'" in sql
    assert "job.claim_token = p_claim_token" in sql
    assert f"revoke all on function {signature}" in sql
    assert f"grant execute on function {signature}" in sql
    assert "to service_role" in sql


def test_safe_rpc_metadata_does_not_return_raw_token_or_fingerprint() -> None:
    sql = migration_sql()
    register_body = sql.split(
        "create or replace function public.register_janani_notification_device", 1
    )[1].split("create or replace function public.list_janani_notification_devices", 1)[0]
    list_body = sql.split("create or replace function public.list_janani_notification_devices", 1)[
        1
    ].split("create or replace function public.revoke_janani_notification_device", 1)[0]
    revoke_body = sql.split(
        "create or replace function public.revoke_janani_notification_device", 1
    )[1].split("create or replace function public.get_janani_notification_destinations", 1)[0]

    for safe_body in (register_body, list_body, revoke_body):
        returned_json = safe_body.rsplit("jsonb_build_object", 1)[-1]
        assert "'push_token'" not in returned_json
        assert "'token_fingerprint'" not in returned_json


def test_destination_lookup_requires_matching_synthetic_data_mode() -> None:
    sql = migration_sql()

    destination_body = sql.split(
        "create or replace function public.get_janani_notification_destinations", 1
    )[1]
    assert "device.synthetic = v_job.synthetic" in destination_body
