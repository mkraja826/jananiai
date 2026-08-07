from pathlib import Path

MIGRATION = Path("supabase/migrations/20260808000000_reminder_delivery_events.sql")


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_delivery_tables_are_rls_protected_and_user_writes_are_closed() -> None:
    sql = migration_sql()

    assert "alter table public.reminder_delivery_jobs enable row level security" in sql
    assert "alter table public.reminder_response_events enable row level security" in sql
    assert "revoke all on public.reminder_delivery_jobs from anon, authenticated" in sql
    assert "revoke all on public.reminder_response_events from anon, authenticated" in sql
    assert "grant select on public.reminder_delivery_jobs to authenticated" in sql
    assert "grant select on public.reminder_response_events to authenticated" in sql


def test_worker_rpcs_are_service_role_only() -> None:
    sql = migration_sql()

    for function_name in (
        "materialize_janani_reminder_deliveries",
        "claim_janani_reminder_deliveries",
        "complete_janani_reminder_delivery",
    ):
        assert f"revoke all on function public.{function_name}" in sql
        assert "to service_role" in sql


def test_delivery_queue_contains_no_clinical_message_payload_columns() -> None:
    sql = migration_sql().lower()
    table_definition = sql.split("create table if not exists public.reminder_delivery_jobs", 1)[1]
    table_definition = table_definition.split(");", 1)[0]

    for prohibited in (
        "medication_name",
        "dose_text",
        "schedule_text",
        "symptom",
        "report_text",
        "prompt",
        "model_output",
        "message_body",
    ):
        assert prohibited not in table_definition


def test_response_events_are_neutral_and_do_not_assert_dose_adherence() -> None:
    sql = migration_sql()

    assert "('opened', 'acknowledged', 'dismissed', 'remind_later')" in sql
    assert "taken" not in sql.lower()
    assert "remind_later requires an explicit future remind_at time" in sql
