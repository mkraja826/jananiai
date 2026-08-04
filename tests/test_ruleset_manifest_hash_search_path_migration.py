from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260804122100_fix_ruleset_manifest_hash_search_path.sql"
)


def test_ruleset_manifest_hash_resolves_pgcrypto_in_locked_search_path() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "approve_janani_clinical_safety_ruleset_internal" in sql
    assert "uuid, text, text[], uuid[], timestamptz, timestamptz, uuid" in sql
    assert "set search_path = public, extensions" in sql
    assert "notify pgrst, 'reload schema'" in sql
