from pathlib import Path

MIGRATION = Path("supabase/migrations/20260807151000_fix_rehearsal_step_validation.sql")


def test_rehearsal_step_extraction_uses_explicit_json_aliases() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "jsonb_array_elements(p_payload -> 'steps') as step_rows(step_item)" in sql
    assert "step_item ->> 'name'" in sql
    assert "unnest(v_step_names) as step_names(step_name)" in sql
    assert "column reference" not in sql


def test_only_fully_passing_evidenced_rehearsals_can_be_recorded() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "only fully passing synthetic rehearsals may be recorded" in sql
    assert "every rehearsal step must pass and contain evidence" in sql
    assert "coalesce((step_item ->> 'passed')::boolean, false) is not true" in sql
    assert "evidence_ref" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "notify pgrst, 'reload schema'" in sql
