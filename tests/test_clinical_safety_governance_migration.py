from pathlib import Path

MIGRATION = Path("supabase/migrations/20260804120000_clinical_safety_governance.sql")


def migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_governance_tables_are_service_role_only() -> None:
    sql = migration_text()

    for table in (
        "clinical_safety_reviewers",
        "clinical_safety_rule_candidates",
        "clinical_safety_rule_reviews",
        "clinical_safety_releases",
        "clinical_safety_release_approvals",
        "clinical_safety_governance_events",
    ):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on table public.{table} from public, anon, authenticated" in sql


def test_release_approval_requires_distinct_clinical_roles() -> None:
    sql = migration_text()

    assert "approve_janani_clinical_safety_release" in sql
    assert "release requires obstetrician and clinical-safety approvals" in sql
    assert "review.reviewer_role = 'obstetrician'" in sql
    assert "review.reviewer_role = 'clinical_safety'" in sql
    assert "development-placeholder sources cannot be approved" in sql
    assert "release cannot outlive sources or reviewer credentials" in sql


def test_reviews_events_and_candidate_content_are_immutable() -> None:
    sql = migration_text()

    assert "prevent_janani_candidate_content_mutation" in sql
    assert "safety rule candidate content is immutable" in sql
    assert "prevent_janani_governance_history_mutation" in sql
    assert "clinical safety governance history is append-only" in sql
    assert "before update or delete on public.clinical_safety_rule_reviews" in sql
    assert "before update or delete on public.clinical_safety_governance_events" in sql


def test_governance_rpcs_are_not_executable_by_end_users() -> None:
    sql = migration_text()

    assert "auth.role() <> 'service_role'" in sql
    assert "record_janani_clinical_rule_review" in sql
    assert "activate_janani_clinical_safety_release" in sql
    assert "rollback_janani_clinical_safety_release" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
