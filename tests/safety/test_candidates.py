from datetime import UTC, datetime, timedelta

import pytest

from app.safety.candidates import build_development_candidates
from app.safety.governance import (
    ClinicalReviewer,
    ReviewDecision,
    ReviewerRole,
    SafetyGovernanceService,
)

NOW = datetime(2026, 8, 4, 0, 0, tzinfo=UTC)


def reviewer(role: ReviewerRole) -> ClinicalReviewer:
    return ClinicalReviewer(
        display_name=f"Synthetic {role.value}",
        role=role,
        license_jurisdiction="IN-synthetic",
        license_reference=f"TEST-{role.value}",
        credential_verified_at=NOW - timedelta(days=30),
        credential_expires_at=NOW + timedelta(days=180),
    )


def test_all_development_rules_become_unique_unapprovable_candidates() -> None:
    candidates = build_development_candidates(created_at=NOW)

    assert len(candidates) == 7
    assert len({item.rule_id for item in candidates}) == 7
    assert len({item.content_digest() for item in candidates}) == 7
    assert all(item.sources[0].development_placeholder for item in candidates)
    assert all(item.created_at == NOW for item in candidates)
    assert all(item.escalation_text.telugu for item in candidates)


def test_placeholder_candidate_cannot_pass_dual_approval() -> None:
    service = SafetyGovernanceService()
    item = build_development_candidates(created_at=NOW)[0]
    obstetrician = reviewer(ReviewerRole.OBSTETRICIAN)
    safety_reviewer = reviewer(ReviewerRole.CLINICAL_SAFETY)
    reviews = (
        service.record_review(
            item,
            obstetrician,
            ReviewDecision.APPROVE,
            "Synthetic review cannot override placeholder provenance.",
            reviewed_at=NOW,
        ),
        service.record_review(
            item,
            safety_reviewer,
            ReviewDecision.APPROVE,
            "Synthetic review cannot override placeholder provenance.",
            reviewed_at=NOW,
        ),
    )

    with pytest.raises(ValueError, match="placeholder"):
        service.approve_release(
            item,
            reviews,
            (obstetrician, safety_reviewer),
            approved_at=NOW,
        )


def test_candidate_builder_defaults_to_timezone_aware_creation_time() -> None:
    item = build_development_candidates()[0]

    assert isinstance(item.created_at, datetime)
    assert item.created_at.utcoffset() is not None
