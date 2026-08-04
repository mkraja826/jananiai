from pathlib import Path

MIGRATION = Path("supabase/migrations/20260804121700_add_ruleset_rpc_json_fallback.sql")


def test_ruleset_approval_has_service_role_json_fallback() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create or replace function public.approve_janani_clinical_safety_ruleset(jsonb)" in sql
    assert "if auth.role() <> 'service_role'" in sql
    assert "jsonb_array_elements_text" in sql
    assert "return public.approve_janani_clinical_safety_ruleset(" in sql
    assert "revoke all on function" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "notify pgrst, 'reload schema'" in sql
