from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260804122000_expose_json_native_ruleset_approval.sql"
)


def test_ruleset_approval_exposes_one_json_native_signature() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "drop function if exists public.approve_janani_clinical_safety_ruleset(jsonb)" in sql
    assert "drop function if exists public.approve_janani_clinical_safety_ruleset_rpc(jsonb)" in sql
    assert "p_required_rule_ids jsonb" in sql
    assert "p_release_ids jsonb" in sql
    assert "jsonb_array_elements_text" in sql
    assert "approve_janani_clinical_safety_ruleset_internal(" in sql
    assert "if auth.role() <> 'service_role'" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "notify pgrst, 'reload schema'" in sql
