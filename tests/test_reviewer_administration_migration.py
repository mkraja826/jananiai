from pathlib import Path

MIGRATION = Path("supabase/migrations/20260805100000_reviewer_administration.sql")


def test_reviewer_administration_schema_is_private_and_audited() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for event_type in (
        "reviewer_onboarded",
        "reviewer_reverified",
        "reviewer_deactivated",
    ):
        assert event_type in sql
    assert "aggregate_type in ('candidate', 'release', 'ruleset', 'reviewer')" in sql
    assert "actor_user_id uuid references auth.users" in sql
    assert "conflict_of_interest_attested_at" in sql
    assert "attestation_version" in sql
    assert "evidence_reference" in sql
    assert "deactivation_reason" in sql


def test_reviewer_updates_require_controlled_rpcs() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "guard_janani_reviewer_administration_update" in sql
    assert "reviewer identity is immutable" in sql
    assert "janani.reviewer_admin_update" in sql
    assert "reviewer administration fields require a controlled rpc" in sql
    assert "perform set_config('janani.reviewer_admin_update', 'allowed', true)" in sql


def test_reviewer_rpcs_are_service_role_only_and_fail_closed() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for function_name in (
        "onboard_janani_clinical_reviewer",
        "reverify_janani_clinical_reviewer",
        "deactivate_janani_clinical_reviewer",
    ):
        assert function_name in sql
    assert sql.count("if auth.role() <> 'service_role'") >= 3
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "conflict-of-interest attestation must precede credential verification" in sql
    assert "reviewer has approvals on an active release" in sql
    assert "notify pgrst, 'reload schema'" in sql
