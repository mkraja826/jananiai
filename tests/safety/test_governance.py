from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.safety.engine import SafetyEngine
from app.safety.governance import (
    ClinicalReviewer,
    ClinicalRuleReview,
    ClinicalSource,
    GovernanceEventType,
    LocalizedEscalationText,
    ReleaseStatus,
    ReviewDecision,
    ReviewerRole,
    RuleApplicability,
    SafetyGovernanceEvent,
    SafetyGovernanceService,
    SafetyRuleCandidate,
    SafetyRuleRelease,
)
from app.safety.models import RuleStatus, SafetySeverity, SymptomAssessmentRequest
from app.safety.rules import SafetyRule

NOW = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=1)


def reviewer(
    role: ReviewerRole,
    *,
    active: bool = True,
    reviewer_id=None,
    verified_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ClinicalReviewer:
    return ClinicalReviewer(
        reviewer_id=reviewer_id or uuid4(),
        display_name=f"Synthetic {role.value}",
        role=role,
        license_jurisdiction="IN-synthetic",
        license_reference=f"TEST-{role.value}",
        credential_verified_at=verified_at or NOW - timedelta(days=30),
        credential_expires_at=expires_at or NOW + timedelta(days=180),
        active=active,
    )


def source(
    *,
    placeholder: bool = False,
    source_id: str = "SRC-001",
    reviewed_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ClinicalSource:
    return ClinicalSource(
        source_id=source_id,
        title="Synthetic clinician review source",
        publisher="Synthetic test publisher",
        reference="synthetic://clinical-source",
        section="Synthetic warning-sign section",
        reviewed_at=reviewed_at or NOW - timedelta(days=30),
        expires_at=expires_at or NOW + timedelta(days=120),
        development_placeholder=placeholder,
    )


def candidate(
    *,
    source_items: tuple[ClinicalSource, ...] | None = None,
    rule_id: str = "TEST-RULE-001",
    version: str = "1.0.0",
) -> SafetyRuleCandidate:
    return SafetyRuleCandidate(
        rule_id=rule_id,
        version=version,
        severity=SafetySeverity.URGENT,
        predicate_key="structured.synthetic.flag",
        clinical_rationale=(
            "Synthetic rationale used only to verify the governance and approval workflow."
        ),
        applicability=RuleApplicability(
            minimum_gestational_week=10,
            maximum_gestational_week=40,
            required_structured_fields=("gestational_week",),
        ),
        escalation_text=LocalizedEscalationText(
            wording_version="draft-1",
            english=(
                "Synthetic escalation wording for engineering tests; contact a qualified "
                "healthcare professional."
            ),
            telugu=("ఇది కేవలం ఇంజినీరింగ్ పరీక్ష కోసం రూపొందించిన నమూనా హెచ్చరిక సందేశం మాత్రమే."),
        ),
        sources=source_items or (source(),),
        created_at=NOW - timedelta(days=1),
    )


def release_payload(**overrides):
    payload = {
        "candidate_id": uuid4(),
        "rule_id": "TEST-RULE",
        "rule_version": "1",
        "candidate_digest": "b" * 64,
        "approval_review_ids": (uuid4(), uuid4()),
        "reviewer_ids": (uuid4(), uuid4()),
        "reviewer_roles": (
            ReviewerRole.OBSTETRICIAN,
            ReviewerRole.CLINICAL_SAFETY,
        ),
        "status": ReleaseStatus.APPROVED,
        "approved_at": NOW,
        "activates_at": NOW,
        "expires_at": NOW + timedelta(days=1),
    }
    payload.update(overrides)
    return payload


def approved_release_bundle():
    service = SafetyGovernanceService()
    item = candidate()
    obstetrician = reviewer(ReviewerRole.OBSTETRICIAN)
    safety_reviewer = reviewer(ReviewerRole.CLINICAL_SAFETY)
    reviews = (
        service.record_review(
            item,
            obstetrician,
            ReviewDecision.APPROVE,
            "Exact candidate content is approved for the synthetic governance test.",
            reviewed_at=NOW,
        ),
        service.record_review(
            item,
            safety_reviewer,
            ReviewDecision.APPROVE,
            "Safety controls and escalation wording are approved for synthetic testing.",
            reviewed_at=NOW,
        ),
    )
    release = service.approve_release(
        item,
        reviews,
        (obstetrician, safety_reviewer),
        approved_at=NOW,
    )
    return service, item, obstetrician, safety_reviewer, reviews, release


def test_applicability_boundaries_and_digest_are_deterministic() -> None:
    item = candidate()
    applicability = item.applicability

    assert applicability.missing_fields(SymptomAssessmentRequest()) == ("gestational_week",)
    assert applicability.applies_to(SymptomAssessmentRequest()) is False
    assert applicability.applies_to(SymptomAssessmentRequest(gestational_week=9)) is False
    assert applicability.applies_to(SymptomAssessmentRequest(gestational_week=41)) is False
    assert applicability.applies_to(SymptomAssessmentRequest(gestational_week=20)) is True

    changed_identity = item.model_copy(
        update={
            "candidate_id": uuid4(),
            "created_at": NOW,
            "status": RuleStatus.UNDER_REVIEW,
        }
    )
    changed_content = item.model_copy(update={"clinical_rationale": item.clinical_rationale + " x"})

    assert changed_identity.content_digest() == item.content_digest()
    assert changed_content.content_digest() != item.content_digest()


def test_happy_path_creates_engine_eligible_dual_approved_metadata() -> None:
    service, item, _, _, reviews, approved = approved_release_bundle()
    active = service.activate_release(approved, activated_at=NOW)
    metadata = service.build_approved_metadata(item, active, checked_at=NOW)
    rule = SafetyRule(metadata=metadata, predicate=lambda payload: payload.heavy_bleeding)
    engine = SafetyEngine((rule,), "governed-test", allow_unapproved=False)
    decision = engine.evaluate(SymptomAssessmentRequest(heavy_bleeding=True))

    assert approved.status is ReleaseStatus.APPROVED
    assert active.status is ReleaseStatus.ACTIVE
    assert approved.expires_at == NOW + timedelta(days=90)
    assert set(approved.reviewer_roles) == {
        ReviewerRole.OBSTETRICIAN,
        ReviewerRole.CLINICAL_SAFETY,
    }
    assert len(set(approved.reviewer_ids)) == 2
    assert {review.review_id for review in reviews} == set(approved.approval_review_ids)
    assert metadata.is_clinically_approved_at(NOW) is True
    assert metadata.governance_content_digest == item.content_digest()
    assert set(metadata.clinician_signoff_ids) == {str(value) for value in active.reviewer_ids}
    assert decision.triggered is True
    assert decision.ruleset_clinically_approved is True


def test_retirement_rollback_and_immutable_event() -> None:
    service, _, _, _, _, approved = approved_release_bundle()
    active = service.activate_release(approved, activated_at=NOW)
    retired = service.retire_release(active, "Superseded after synthetic review")
    prior = approved.model_copy(
        update={
            "release_id": uuid4(),
            "status": ReleaseStatus.RETIRED,
            "expires_at": NOW + timedelta(days=30),
        }
    )
    rolled_back, replacement = service.rollback_release(
        active,
        prior,
        "Synthetic regression detected",
        rolled_back_at=NOW + timedelta(days=1),
    )
    event = SafetyGovernanceEvent(
        event_type=GovernanceEventType.RELEASE_ROLLED_BACK,
        aggregate_id=active.release_id,
        actor_id=active.reviewer_ids[0],
        occurred_at=NOW + timedelta(days=1),
        reason="Synthetic regression detected",
        prior_status=ReleaseStatus.ACTIVE,
        new_status=ReleaseStatus.ROLLED_BACK,
        content_digest=active.candidate_digest,
    )

    assert retired.status is ReleaseStatus.RETIRED
    assert retired.terminal_reason
    assert rolled_back.status is ReleaseStatus.ROLLED_BACK
    assert replacement.status is ReleaseStatus.ACTIVE
    assert event.event_type is GovernanceEventType.RELEASE_ROLLED_BACK
    with pytest.raises(ValidationError):
        event.reason = "mutated"


def test_reviewer_source_applicability_and_candidate_validation() -> None:
    naive = datetime(2026, 8, 4)
    with pytest.raises(ValidationError, match="timezone"):
        reviewer(ReviewerRole.OBSTETRICIAN, verified_at=naive, expires_at=naive + timedelta(1))
    with pytest.raises(ValidationError, match="follow verification"):
        reviewer(
            ReviewerRole.OBSTETRICIAN,
            verified_at=NOW,
            expires_at=NOW - timedelta(seconds=1),
        )
    with pytest.raises(ValidationError, match="timezone"):
        source(reviewed_at=naive, expires_at=naive + timedelta(1))
    with pytest.raises(ValidationError, match="follow source review"):
        source(reviewed_at=NOW, expires_at=NOW)
    with pytest.raises(ValidationError, match="cannot exceed"):
        RuleApplicability(minimum_gestational_week=20, maximum_gestational_week=10)
    with pytest.raises(ValidationError, match="Unknown structured"):
        RuleApplicability(required_structured_fields=("free_text_diagnosis",))
    with pytest.raises(ValidationError, match="unique"):
        RuleApplicability(required_structured_fields=("gestational_week", "gestational_week"))

    approved_payload = candidate().model_dump()
    approved_payload["status"] = RuleStatus.APPROVED
    with pytest.raises(ValidationError, match="draft or under review"):
        SafetyRuleCandidate.model_validate(approved_payload)

    duplicate_source = source()
    with pytest.raises(ValidationError, match="source IDs"):
        candidate(source_items=(duplicate_source, duplicate_source))

    naive_payload = candidate().model_dump(exclude={"created_at"})
    with pytest.raises(ValidationError, match="creation time"):
        SafetyRuleCandidate(**naive_payload, created_at=naive)


def test_review_and_release_model_validation() -> None:
    with pytest.raises(ValidationError, match="Review time"):
        ClinicalRuleReview(
            candidate_id=uuid4(),
            candidate_digest="a" * 64,
            reviewer_id=uuid4(),
            reviewer_role=ReviewerRole.OBSTETRICIAN,
            decision=ReviewDecision.APPROVE,
            rationale="Synthetic approval rationale",
            reviewed_at=datetime(2026, 8, 4),
        )

    with pytest.raises(ValidationError, match="cannot precede"):
        SafetyRuleRelease(**release_payload(activates_at=NOW - timedelta(seconds=1)))
    with pytest.raises(ValidationError, match="follow activation"):
        SafetyRuleRelease(**release_payload(expires_at=NOW))
    duplicate_review = uuid4()
    with pytest.raises(ValidationError, match="review IDs"):
        SafetyRuleRelease(
            **release_payload(approval_review_ids=(duplicate_review, duplicate_review))
        )
    duplicate_reviewer = uuid4()
    with pytest.raises(ValidationError, match="distinct reviewers"):
        SafetyRuleRelease(**release_payload(reviewer_ids=(duplicate_reviewer, duplicate_reviewer)))


def test_record_review_rejects_invalid_state_or_credentials() -> None:
    service = SafetyGovernanceService()
    item = candidate()
    valid = reviewer(ReviewerRole.OBSTETRICIAN)
    approved_candidate = item.model_copy(update={"status": RuleStatus.APPROVED})

    with pytest.raises(ValueError, match="draft or under-review"):
        service.record_review(
            approved_candidate,
            valid,
            ReviewDecision.APPROVE,
            "Synthetic approval rationale",
            reviewed_at=NOW,
        )

    invalid_reviewers = (
        reviewer(ReviewerRole.OBSTETRICIAN, active=False),
        reviewer(
            ReviewerRole.OBSTETRICIAN,
            verified_at=NOW - timedelta(days=10),
            expires_at=NOW - timedelta(seconds=1),
        ),
    )
    for invalid in invalid_reviewers:
        with pytest.raises(ValueError, match="credentials"):
            service.record_review(
                item,
                invalid,
                ReviewDecision.APPROVE,
                "Synthetic approval rationale",
                reviewed_at=NOW,
            )


def test_release_rejects_placeholder_expired_or_unbound_content() -> None:
    service, item, obstetrician, safety_reviewer, reviews, _ = approved_release_bundle()

    for bad_source, expected in (
        (source(placeholder=True), "placeholder"),
        (
            source(
                reviewed_at=NOW - timedelta(days=20),
                expires_at=NOW - timedelta(seconds=1),
            ),
            "current",
        ),
    ):
        bad_item = candidate(source_items=(bad_source,))
        bad_reviews = (
            service.record_review(
                bad_item,
                obstetrician,
                ReviewDecision.APPROVE,
                "Synthetic obstetric approval rationale",
                reviewed_at=NOW,
            ),
            service.record_review(
                bad_item,
                safety_reviewer,
                ReviewDecision.APPROVE,
                "Synthetic safety approval rationale",
                reviewed_at=NOW,
            ),
        )
        with pytest.raises(ValueError, match=expected):
            service.approve_release(
                bad_item,
                bad_reviews,
                (obstetrician, safety_reviewer),
                approved_at=NOW,
            )

    with pytest.raises(ValueError, match="At least two"):
        service.approve_release(
            item,
            (),
            (obstetrician, safety_reviewer),
            approved_at=NOW,
        )

    wrong_id = reviews[0].model_copy(update={"candidate_id": uuid4()})
    with pytest.raises(ValueError, match="candidate IDs"):
        service.approve_release(
            item,
            (wrong_id, reviews[1]),
            (obstetrician, safety_reviewer),
            approved_at=NOW,
        )

    wrong_digest = reviews[0].model_copy(update={"candidate_digest": "f" * 64})
    with pytest.raises(ValueError, match="different candidate content"):
        service.approve_release(
            item,
            (wrong_digest, reviews[1]),
            (obstetrician, safety_reviewer),
            approved_at=NOW,
        )

    rejected = reviews[0].model_copy(update={"decision": ReviewDecision.REQUEST_CHANGES})
    with pytest.raises(ValueError, match="must approve"):
        service.approve_release(
            item,
            (rejected, reviews[1]),
            (obstetrician, safety_reviewer),
            approved_at=NOW,
        )


def test_release_requires_distinct_reviewers_roles_and_current_registry() -> None:
    service, item, obstetrician, safety_reviewer, reviews, _ = approved_release_bundle()

    duplicate_identity = reviews[1].model_copy(
        update={
            "reviewer_id": reviews[0].reviewer_id,
            "reviewer_role": reviews[0].reviewer_role,
        }
    )
    with pytest.raises(ValueError, match="distinct reviewers"):
        service.approve_release(
            item,
            (reviews[0], duplicate_identity),
            (obstetrician, safety_reviewer),
            approved_at=NOW,
        )

    second_obstetrician = reviewer(ReviewerRole.OBSTETRICIAN)
    second_ob_review = service.record_review(
        item,
        second_obstetrician,
        ReviewDecision.APPROVE,
        "Second synthetic obstetric approval rationale",
        reviewed_at=NOW,
    )
    with pytest.raises(ValueError, match="Missing required approval roles"):
        service.approve_release(
            item,
            (reviews[0], second_ob_review),
            (obstetrician, second_obstetrician),
            approved_at=NOW,
        )

    with pytest.raises(ValueError, match="duplicate identities"):
        service.approve_release(
            item,
            reviews,
            (obstetrician, obstetrician),
            approved_at=NOW,
        )
    with pytest.raises(ValueError, match="unknown reviewer"):
        service.approve_release(
            item,
            reviews,
            (obstetrician,),
            approved_at=NOW,
        )

    role_mismatch = reviewer(
        ReviewerRole.LANGUAGE_REVIEWER,
        reviewer_id=safety_reviewer.reviewer_id,
    )
    with pytest.raises(ValueError, match="role does not match"):
        service.approve_release(
            item,
            reviews,
            (obstetrician, role_mismatch),
            approved_at=NOW,
        )

    expired_safety = reviewer(
        ReviewerRole.CLINICAL_SAFETY,
        reviewer_id=safety_reviewer.reviewer_id,
        verified_at=NOW - timedelta(days=30),
        expires_at=NOW - timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="current credentials"):
        service.approve_release(
            item,
            reviews,
            (obstetrician, expired_safety),
            approved_at=NOW,
        )

    with pytest.raises(ValueError, match="cannot outlive"):
        service.approve_release(
            item,
            reviews,
            (obstetrician, safety_reviewer),
            approved_at=NOW,
            expires_at=NOW + timedelta(days=121),
        )


def test_lifecycle_and_metadata_methods_fail_closed() -> None:
    service, item, _, _, _, approved = approved_release_bundle()

    with pytest.raises(ValueError, match="Only approved"):
        service.activate_release(
            approved.model_copy(update={"status": ReleaseStatus.RETIRED}),
            activated_at=NOW,
        )
    with pytest.raises(ValueError, match="window has not started"):
        service.activate_release(
            approved.model_copy(update={"activates_at": NOW + timedelta(days=1)}),
            activated_at=NOW,
        )
    with pytest.raises(ValueError, match="Expired"):
        service.activate_release(
            approved.model_copy(update={"expires_at": NOW}),
            activated_at=NOW,
        )
    with pytest.raises(ValueError, match="approved or active"):
        service.retire_release(
            approved.model_copy(update={"status": ReleaseStatus.ROLLED_BACK}),
            "Synthetic reason",
        )

    active = service.activate_release(approved, activated_at=NOW)
    prior = approved.model_copy(
        update={
            "release_id": uuid4(),
            "status": ReleaseStatus.RETIRED,
            "expires_at": NOW + timedelta(days=10),
        }
    )
    with pytest.raises(ValueError, match="Only an active"):
        service.rollback_release(approved, prior, "Synthetic rollback", rolled_back_at=NOW)
    with pytest.raises(ValueError, match="same rule"):
        service.rollback_release(
            active,
            prior.model_copy(update={"rule_id": "OTHER-RULE"}),
            "Synthetic rollback",
            rolled_back_at=NOW,
        )
    with pytest.raises(ValueError, match="approved prior"):
        service.rollback_release(
            active,
            prior.model_copy(update={"status": ReleaseStatus.ACTIVE}),
            "Synthetic rollback",
            rolled_back_at=NOW,
        )
    with pytest.raises(ValueError, match="expired"):
        service.rollback_release(
            active,
            prior.model_copy(update={"expires_at": NOW}),
            "Synthetic rollback",
            rolled_back_at=NOW,
        )

    with pytest.raises(ValueError, match="active governance"):
        service.build_approved_metadata(item, approved, checked_at=NOW)
    with pytest.raises(ValueError, match="identities"):
        service.build_approved_metadata(
            item.model_copy(update={"candidate_id": uuid4()}),
            active,
            checked_at=NOW,
        )
    with pytest.raises(ValueError, match="digest"):
        service.build_approved_metadata(
            item.model_copy(update={"clinical_rationale": item.clinical_rationale + " changed"}),
            active,
            checked_at=NOW,
        )
    with pytest.raises(ValueError, match="activation window"):
        service.build_approved_metadata(item, active, checked_at=active.expires_at)
