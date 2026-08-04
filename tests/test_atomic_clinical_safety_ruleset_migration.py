from pathlib import Path

MIGRATION = Path("supabase/migrations/20260804121500_atomic_clinical_safety_rulesets.sql")


def test_atomic_ruleset_schema_is_private_immutable_and_complete() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists public.clinical_safety_rulesets" in sql
    assert "create table if not exists public.clinical_safety_ruleset_members" in sql
    assert "required_rule_ids text[] not null" in sql
    assert "manifest_digest text not null unique" in sql
    assert "one_active_clinical_safety_ruleset" in sql
    assert "prevent_janani_ruleset_content_mutation" in sql
    assert "prevent_clinical_safety_ruleset_member_mutation" in sql
    assert "revoke all on table public.clinical_safety_rulesets" in sql
    assert "revoke all on table public.clinical_safety_ruleset_members" in sql


def test_atomic_ruleset_rpcs_are_service_role_only_and_fail_closed() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "approve_janani_clinical_safety_ruleset" in sql
    assert "activate_janani_clinical_safety_ruleset" in sql
    assert "rollback_janani_clinical_safety_ruleset" in sql
    assert "ruleset releases must exactly match required rule ids" in sql
    assert "active release drift detected without an active ruleset" in sql
    assert "current active ruleset and active releases have drifted" in sql
    assert "atomic ruleset activation failed final consistency check" in sql
    assert "atomic ruleset rollback failed final consistency check" in sql
    assert sql.count("if auth.role() <> 'service_role'") >= 3
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql


def test_ruleset_events_cover_approval_activation_retirement_and_rollback() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for event_type in (
        "ruleset_approved",
        "ruleset_activated",
        "ruleset_retired",
        "ruleset_rolled_back",
    ):
        assert event_type in sql
    assert "aggregate_type in ('candidate', 'release', 'ruleset')" in sql
