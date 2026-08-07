from pathlib import Path

MIGRATION = Path("supabase/migrations/20260807180000_lifecycle_reminders_upload_integrity.sql")


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_phase9_tables_are_rls_protected_and_user_writes_are_rpc_only() -> None:
    sql = migration_sql()
    for table in (
        "pregnancy_completion_events",
        "medication_reminder_schedules",
        "appointment_reminder_schedules",
        "attachment_upload_intents",
    ):
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on public.{table} from anon, authenticated" in sql
        assert f"grant select on public.{table} to authenticated" in sql

    assert "revoke insert, update, delete on public.attachment_records from authenticated" in sql


def test_reminders_are_explicit_and_bound_to_owned_records() -> None:
    sql = migration_sql()
    assert "create_janani_medication_reminder" in sql
    assert "medication.active" in sql
    assert "medication.confirmed" in sql
    assert "pg_timezone_names" in sql
    assert "create_janani_appointment_reminder" in sql
    assert "appointment.status = 'scheduled'" in sql
    assert "schedule_text" not in sql
    assert "dose_text" not in sql


def test_attachment_handshake_freezes_finalized_objects_and_gates_extraction() -> None:
    sql = migration_sql()
    assert "request_janani_attachment_upload" in sql
    assert "finalize_janani_attachment_upload" in sql
    assert "verify_janani_attachment_integrity" in sql
    assert "pending_worker_hash" in sql
    assert "attachment integrity must be verified before extraction" in sql
    assert "not exists (\n    select 1\n    from public.attachment_records attachment" in sql
    assert "file_size_limit = 20971520" in sql
    for mime_type in ("application/pdf", "image/jpeg", "image/png", "image/webp"):
        assert mime_type in sql


def test_completion_is_append_only_and_atomically_closes_episode() -> None:
    sql = migration_sql()
    assert "pregnancy_completion_events" in sql
    assert "supersedes_completion_event_id" in sql
    assert "only an active pregnancy can receive its first completion event" in sql
    assert "status = 'completed'" in sql
    assert "completed_at = p_occurred_at" in sql
