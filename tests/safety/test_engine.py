from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.safety.engine import SafetyEngine
from app.safety.models import (
    RuleMetadata,
    RuleStatus,
    SafetySeverity,
    SymptomAssessmentRequest,
)
from app.safety.rules import build_development_rules


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("seizure", SafetySeverity.EMERGENCY),
        ("loss_of_consciousness", SafetySeverity.EMERGENCY),
        ("severe_breathing_difficulty", SafetySeverity.EMERGENCY),
        ("heavy_bleeding", SafetySeverity.URGENT),
        ("severe_abdominal_pain", SafetySeverity.URGENT),
        ("reduced_fetal_movement", SafetySeverity.URGENT),
    ],
)
def test_each_draft_rule_triggers_in_synthetic_development_mode(
    field: str,
    expected: SafetySeverity,
) -> None:
    engine = SafetyEngine(build_development_rules(), "test", allow_unapproved=True)
    payload = SymptomAssessmentRequest(**{field: True})

    decision = engine.evaluate(payload)

    assert decision.triggered is True
    assert decision.severity is expected
    assert decision.blocks_llm is True
    assert decision.development_only is True


def test_headache_requires_vision_changes_for_draft_combination() -> None:
    engine = SafetyEngine(build_development_rules(), "test", allow_unapproved=True)

    headache_only = engine.evaluate(SymptomAssessmentRequest(severe_headache=True))
    combined = engine.evaluate(SymptomAssessmentRequest(severe_headache=True, vision_changes=True))

    assert headache_only.triggered is False
    assert combined.triggered is True
    assert "DEV-HEADACHE-VISION-001" in combined.triggered_rule_ids


def test_emergency_takes_precedence_over_urgent() -> None:
    engine = SafetyEngine(build_development_rules(), "test", allow_unapproved=True)
    payload = SymptomAssessmentRequest(seizure=True, heavy_bleeding=True)

    decision = engine.evaluate(payload)

    assert decision.severity is SafetySeverity.EMERGENCY
    assert len(decision.triggered_rule_ids) == 2


def test_no_match_does_not_claim_safety() -> None:
    engine = SafetyEngine(build_development_rules(), "test", allow_unapproved=True)

    decision = engine.evaluate(SymptomAssessmentRequest())

    assert decision.triggered is False
    assert decision.severity is SafetySeverity.ROUTINE
    assert "does not establish" in decision.message
    assert decision.blocks_llm is False


def test_production_mode_ignores_unapproved_rules() -> None:
    engine = SafetyEngine(build_development_rules(), "production", allow_unapproved=False)

    decision = engine.evaluate(SymptomAssessmentRequest(seizure=True))

    assert decision.triggered is False
    assert decision.severity is SafetySeverity.INSUFFICIENT_INFORMATION
    assert decision.blocks_llm is True
    assert engine.clinical_ready is False


def approved_metadata(approved_at: datetime) -> RuleMetadata:
    return RuleMetadata(
        rule_id="TEST-APPROVED-001",
        version="1.0.0",
        status=RuleStatus.APPROVED,
        severity=SafetySeverity.EMERGENCY,
        response_template="Approved test escalation.",
        clinician_signoff_ids=("synthetic-obstetrician", "synthetic-safety-reviewer"),
        governance_release_id="synthetic-release-id",
        governance_content_digest="a" * 64,
        approved_at=approved_at,
        next_review_at=approved_at + timedelta(days=30),
    )


def test_dual_approved_rule_can_run_without_development_override() -> None:
    draft = build_development_rules()[0]
    approved_at = datetime.now(UTC)
    approved = replace(draft, metadata=approved_metadata(approved_at))
    engine = SafetyEngine((approved,), "approved-test", allow_unapproved=False)

    decision = engine.evaluate(SymptomAssessmentRequest(seizure=True))

    assert decision.triggered is True
    assert decision.ruleset_clinically_approved is True
    assert decision.development_only is False
    assert engine.clinical_ready is True


def test_approved_status_rejects_incomplete_governance_metadata() -> None:
    with pytest.raises(ValidationError, match="two distinct"):
        RuleMetadata(
            rule_id="TEST-INCOMPLETE-001",
            version="1.0.0",
            status=RuleStatus.APPROVED,
            severity=SafetySeverity.URGENT,
            response_template="Incomplete approval must fail.",
            clinician_signoff_ids=("one-reviewer",),
        )


def test_approved_status_rejects_missing_release_binding() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="governance release"):
        RuleMetadata(
            rule_id="TEST-INCOMPLETE-002",
            version="1.0.0",
            status=RuleStatus.APPROVED,
            severity=SafetySeverity.URGENT,
            response_template="Incomplete approval must fail.",
            clinician_signoff_ids=("reviewer-a", "reviewer-b"),
            approved_at=now,
            next_review_at=now + timedelta(days=1),
        )


def test_approval_window_is_time_bounded() -> None:
    approved_at = datetime.now(UTC) - timedelta(days=10)
    metadata = approved_metadata(approved_at)

    assert metadata.is_clinically_approved_at(approved_at + timedelta(days=1)) is True
    assert metadata.is_clinically_approved_at(approved_at + timedelta(days=31)) is False


def test_approved_status_rejects_naive_or_inverted_timestamps() -> None:
    naive = datetime.now()
    with pytest.raises(ValidationError, match="timezone"):
        RuleMetadata(
            rule_id="TEST-INCOMPLETE-003",
            version="1.0.0",
            status=RuleStatus.APPROVED,
            severity=SafetySeverity.URGENT,
            response_template="Incomplete approval must fail.",
            clinician_signoff_ids=("reviewer-a", "reviewer-b"),
            governance_release_id="release",
            governance_content_digest="b" * 64,
            approved_at=naive,
            next_review_at=naive + timedelta(days=1),
        )

    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="later"):
        RuleMetadata(
            rule_id="TEST-INCOMPLETE-004",
            version="1.0.0",
            status=RuleStatus.APPROVED,
            severity=SafetySeverity.URGENT,
            response_template="Incomplete approval must fail.",
            clinician_signoff_ids=("reviewer-a", "reviewer-b"),
            governance_release_id="release",
            governance_content_digest="c" * 64,
            approved_at=now,
            next_review_at=now,
        )
