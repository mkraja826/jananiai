from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260804120500_tighten_clinical_release_approvals.sql"
)


def test_each_release_approval_revalidates_identity_digest_role_and_credentials() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "validate_janani_clinical_release_approval" in sql
    assert "v_review.candidate_digest <> v_release.candidate_digest" in sql
    assert "v_review.reviewer_id <> new.reviewer_id" in sql
    assert "v_reviewer.role <> new.reviewer_role" in sql
    assert "v_reviewer.credential_expires_at <= v_release.approved_at" in sql
    assert "before insert on public.clinical_safety_release_approvals" in sql
