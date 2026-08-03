from pathlib import Path

MIGRATION = Path("supabase/migrations/20260804113000_authenticated_persistence.sql")


def migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_internal_writes_are_exposed_only_through_authenticated_rpcs() -> None:
    sql = migration_text()

    assert "security definer" in sql
    assert "auth.uid()" in sql
    assert "record_janani_safety_event" in sql
    assert "record_janani_context_event" in sql
    assert "revoke insert, update, delete on public.context_assembly_events" in sql
    assert "revoke insert, update, delete on public.safety_audit_events" in sql
    assert "grant execute on function public.record_janani_context_event" in sql


def test_consent_remains_append_only_for_authenticated_clients() -> None:
    sql = migration_text()

    assert "grant select, insert on public.consent_events to authenticated" in sql
    assert "revoke update, delete on public.consent_events from authenticated" in sql


def test_account_deletion_is_a_request_workflow_not_immediate_data_loss() -> None:
    sql = migration_text()

    assert "create table if not exists public.account_deletion_requests" in sql
    assert "request_janani_account_deletion" in sql
    assert "actual deletion is a later controlled job" in sql
