from pathlib import Path

MIGRATION = Path("supabase/migrations/20260804121800_disambiguate_ruleset_approval_rpc.sql")


def test_ruleset_approval_has_one_public_postgrest_signature() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "rename to approve_janani_clinical_safety_ruleset_internal" in sql
    assert "drop function if exists public.approve_janani_clinical_safety_ruleset(jsonb)" in sql
    assert "create function public.approve_janani_clinical_safety_ruleset(jsonb)" in sql
    assert "approve_janani_clinical_safety_ruleset_internal(" in sql
    assert "if auth.role() <> 'service_role'" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "notify pgrst, 'reload schema'" in sql
