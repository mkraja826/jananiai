from pathlib import Path

MIGRATION = Path("supabase/migrations/20260808020000_expo_push_transport.sql")


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_expo_transport_is_added_without_opening_raw_device_table() -> None:
    sql = migration_sql()

    assert "check (transport in ('mock', 'expo'))" in sql
    assert "p_transport not in ('mock', 'expo')" in sql
    assert "p_transport = 'expo' and p_platform = 'web'" in sql
    assert "Invalid Expo push token" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "token_fingerprint" in sql


def test_registration_rpc_remains_authenticated_only() -> None:
    sql = migration_sql()

    signature = (
        "public.register_janani_notification_device(uuid, text, text, text, boolean)"
    )
    assert f"revoke all on function {signature}" in sql
    assert "from public, anon;" in sql
    assert f"grant execute on function {signature}" in sql
    assert "to authenticated;" in sql
