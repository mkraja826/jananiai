from pathlib import Path

MIGRATION = Path("supabase/migrations/20260807170000_structured_pregnancy_timeline.sql")


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_timeline_tables_are_rls_protected_and_append_only_for_users() -> None:
    sql = migration_sql()

    assert "alter table public.pregnancy_observations enable row level security" in sql
    assert "alter table public.pregnancy_encounters enable row level security" in sql
    assert "grant select, insert on public.pregnancy_observations to authenticated" in sql
    assert "grant select, insert on public.pregnancy_encounters to authenticated" in sql
    assert "grant update" not in "\n".join(
        line for line in sql.splitlines() if "pregnancy_observations to authenticated" in line
    )
    assert "grant update" not in "\n".join(
        line for line in sql.splitlines() if "pregnancy_encounters to authenticated" in line
    )


def test_timeline_links_are_checked_at_database_boundary() -> None:
    sql = migration_sql()

    assert "enforce_janani_observation_links" in sql
    assert "enforce_janani_encounter_links" in sql
    assert "source attachment does not belong to pregnancy owner" in sql
    assert "superseded observation does not belong to pregnancy owner" in sql
    assert "superseded encounter does not belong to pregnancy owner" in sql


def test_attachment_metadata_has_integrity_fields_without_report_text() -> None:
    sql = migration_sql()

    for column in (
        "document_date",
        "display_label",
        "capture_source",
        "file_size_bytes",
        "content_sha256",
    ):
        assert column in sql
    assert "extracted_text" not in sql
