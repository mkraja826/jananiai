from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.safety.candidates import build_development_candidates
from app.safety.engine import SafetyEngine
from app.safety.governance import ReviewDecision, ReviewerRole
from app.safety.review_packets import (
    ClinicalReviewPacketBuilder,
    ReviewPacketAttestation,
    ReviewPacketStatus,
    RuleValidationEvidence,
)
from app.safety.rules import DEVELOPMENT_RULESET_VERSION, build_development_rules
from app.safety.validation import (
    REQUIRED_CASE_CATEGORIES,
    SafetyValidationRunner,
    build_development_validation_dataset,
)

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def validation_inputs():
    dataset = build_development_validation_dataset()
    engine = SafetyEngine(
        rules=build_development_rules(),
        ruleset_version=DEVELOPMENT_RULESET_VERSION,
        allow_unapproved=True,
    )
    report = SafetyValidationRunner().run(dataset, engine)
    candidate = build_development_candidates(created_at=NOW)[0]
    return candidate, dataset, report


def test_builder_binds_candidate_to_exact_passing_dataset() -> None:
    candidate, dataset, report = validation_inputs()

    packet = ClinicalReviewPacketBuilder().build(
        candidate,
        dataset,
        report,
        generated_at=NOW,
    )

    assert packet.status is ReviewPacketStatus.CLINICAL_INPUT_REQUIRED
    assert packet.synthetic_only
    assert packet.rule_id == candidate.rule_id
    assert packet.candidate_digest == candidate.content_digest()
    assert packet.validation.dataset_version == dataset.dataset_version
    assert packet.validation.total_cases == 9
    assert packet.validation.passed_cases == 9
    assert set(packet.validation.categories) == {
        category.value for category in REQUIRED_CASE_CATEGORIES
    }
    assert packet.placeholder_sources_present
    assert not packet.clinical_approval_eligible
    assert len(packet.content_digest()) == 64


def test_packet_digest_changes_when_review_content_changes() -> None:
    candidate, dataset, report = validation_inputs()
    packet = ClinicalReviewPacketBuilder().build(candidate, dataset, report, generated_at=NOW)

    changed = packet.model_copy(
        update={"clinical_rationale": packet.clinical_rationale + " Updated."}
    )

    assert packet.content_digest() != changed.content_digest()


def test_builder_rejects_failed_or_mismatched_validation_report() -> None:
    candidate, dataset, report = validation_inputs()
    failed = report.model_copy(update={"failed_cases": 1, "passed_cases": report.passed_cases - 1})

    with pytest.raises(ValueError, match="fully passing"):
        ClinicalReviewPacketBuilder().build(candidate, dataset, failed, generated_at=NOW)

    wrong_version = report.model_copy(update={"dataset_version": "different"})
    with pytest.raises(ValueError, match="dataset version"):
        ClinicalReviewPacketBuilder().build(candidate, dataset, wrong_version, generated_at=NOW)


def test_evidence_requires_every_category_and_every_case_to_pass() -> None:
    category_names = tuple(sorted(category.value for category in REQUIRED_CASE_CATEGORIES))

    with pytest.raises(ValidationError, match="every engineering case"):
        RuleValidationEvidence(
            rule_id="DEV-SEIZURE-001",
            dataset_version="dataset-1",
            dataset_digest="a" * 64,
            case_ids=tuple(f"case-{index}" for index in range(9)),
            categories=category_names,
            total_cases=9,
            passed_cases=8,
        )

    with pytest.raises(ValidationError, match="every required validation category"):
        RuleValidationEvidence(
            rule_id="DEV-SEIZURE-001",
            dataset_version="dataset-1",
            dataset_digest="a" * 64,
            case_ids=tuple(f"case-{index}" for index in range(8)),
            categories=category_names[:-1],
            total_cases=8,
            passed_cases=8,
        )


def test_approval_attestation_requires_all_evidence_confirmations() -> None:
    with pytest.raises(ValidationError, match="all evidence confirmations"):
        ReviewPacketAttestation(
            packet_digest="a" * 64,
            reviewer_id=uuid4(),
            reviewer_role=ReviewerRole.OBSTETRICIAN,
            decision=ReviewDecision.APPROVE,
            confirms_expected_results=True,
            confirms_sources_and_sections=False,
            confirms_escalation_wording=True,
            rationale="Synthetic reviewer approval contract validation only.",
            reviewed_at=NOW,
        )


def test_non_approval_attestation_can_request_changes_without_confirming_evidence() -> None:
    attestation = ReviewPacketAttestation(
        packet_digest="b" * 64,
        reviewer_id=uuid4(),
        reviewer_role=ReviewerRole.LANGUAGE_REVIEWER,
        decision=ReviewDecision.REQUEST_CHANGES,
        confirms_expected_results=False,
        confirms_sources_and_sections=False,
        confirms_escalation_wording=False,
        rationale="Synthetic language reviewer requests wording changes before approval.",
        reviewed_at=NOW,
    )

    assert attestation.decision is ReviewDecision.REQUEST_CHANGES
    assert attestation.synthetic_rehearsal
