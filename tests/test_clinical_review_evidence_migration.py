from pathlib import Path

MIGRATION = Path("supabase/migrations/20260807150000_clinical_review_evidence.sql")


def test_review_evidence_tables_are_private_and_immutable() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists public.clinical_safety_review_packets" in sql
    assert "create table if not exists public.clinical_safety_rehearsals" in sql
    assert "prevent_clinical_safety_review_packet_mutation" in sql
    assert "prevent_clinical_safety_rehearsal_mutation" in sql
    assert "revoke all on table public.clinical_safety_review_packets" in sql
    assert "revoke all on table public.clinical_safety_rehearsals" in sql
    assert "grant select on table public.clinical_safety_review_packets to service_role" in sql
    assert "grant select on table public.clinical_safety_rehearsals to service_role" in sql


def test_review_packet_rpc_is_service_role_only_and_fully_passing() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "record_janani_clinical_review_packet" in sql
    assert "if auth.role() <> 'service_role'" in sql
    assert "review packet requires fully passing validation evidence" in sql
    assert "review packet validation categories are incomplete" in sql
    assert "review packet candidate binding does not match stored content" in sql
    assert "current review packet persistence is synthetic-only" in sql


def test_rehearsal_rpc_requires_exact_atomic_rollback_evidence() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "record_janani_safety_rehearsal" in sql
    assert "restored rehearsal ruleset is not active" in sql
    assert "incident ruleset is not in rolled-back state" in sql
    assert "rehearsal steps are incomplete" in sql
    assert "current rehearsal persistence is synthetic-only" in sql
    assert "review_packet_recorded" in sql
    assert "rehearsal_recorded" in sql
    assert "notify pgrst, 'reload schema'" in sql
