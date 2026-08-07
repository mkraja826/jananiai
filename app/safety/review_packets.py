"""Immutable pre-clinical review packets for deterministic safety candidates.

A packet binds one rule candidate to the exact engineering-validation dataset
and result summary that a qualified reviewer is asked to inspect. These models
do not create clinical approval; they make the evidence package reproducible
and fail closed when engineering validation is incomplete.
"""

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.safety.governance import ReviewDecision, ReviewerRole, SafetyRuleCandidate
from app.safety.validation import (
    REQUIRED_CASE_CATEGORIES,
    SafetyRuleValidationDataset,
    SafetyValidationReport,
)


class ReviewPacketStatus(StrEnum):
    ENGINEERING_READY = "engineering_ready"
    CLINICAL_INPUT_REQUIRED = "clinical_input_required"
    CHANGES_REQUIRED = "changes_required"


class FrozenReviewPacketModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RuleValidationEvidence(FrozenReviewPacketModel):
    rule_id: Annotated[str, Field(min_length=3, max_length=120)]
    dataset_version: Annotated[str, Field(min_length=1, max_length=80)]
    dataset_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    case_ids: Annotated[tuple[str, ...], Field(min_length=1)]
    categories: Annotated[tuple[str, ...], Field(min_length=1)]
    total_cases: Annotated[int, Field(gt=0)]
    passed_cases: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_evidence(self) -> "RuleValidationEvidence":
        if len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError("Review evidence case IDs must be unique")
        if self.passed_cases != self.total_cases:
            raise ValueError("Review evidence requires every engineering case to pass")
        required = {category.value for category in REQUIRED_CASE_CATEGORIES}
        if set(self.categories) != required:
            raise ValueError("Review evidence must contain every required validation category")
        return self


class SafetyClinicalReviewPacket(FrozenReviewPacketModel):
    packet_id: UUID = Field(default_factory=uuid4)
    packet_version: Annotated[str, Field(min_length=1, max_length=80)]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    candidate_id: UUID
    rule_id: Annotated[str, Field(min_length=3, max_length=120)]
    candidate_version: Annotated[str, Field(min_length=1, max_length=40)]
    candidate_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    severity: str
    predicate_key: str
    clinical_rationale: str
    source_references: Annotated[tuple[str, ...], Field(min_length=1)]
    placeholder_sources_present: bool
    escalation_wording_version: str
    english_escalation_text: str
    telugu_escalation_text: str
    validation: RuleValidationEvidence
    required_review_roles: tuple[ReviewerRole, ...] = (
        ReviewerRole.OBSTETRICIAN,
        ReviewerRole.CLINICAL_SAFETY,
        ReviewerRole.LANGUAGE_REVIEWER,
    )
    status: ReviewPacketStatus = ReviewPacketStatus.CLINICAL_INPUT_REQUIRED
    synthetic_only: bool = True

    @model_validator(mode="after")
    def validate_packet(self) -> "SafetyClinicalReviewPacket":
        if self.generated_at.utcoffset() is None:
            raise ValueError("Review packet generation time must include timezone information")
        if not self.synthetic_only:
            raise ValueError("Current review packets are synthetic/pre-clinical only")
        if self.validation.rule_id != self.rule_id:
            raise ValueError("Validation evidence rule ID must match the packet rule")
        if len(set(self.source_references)) != len(self.source_references):
            raise ValueError("Review packet source references must be unique")
        if len(set(self.required_review_roles)) != len(self.required_review_roles):
            raise ValueError("Required review roles must be unique")
        required_roles = {
            ReviewerRole.OBSTETRICIAN,
            ReviewerRole.CLINICAL_SAFETY,
            ReviewerRole.LANGUAGE_REVIEWER,
        }
        if set(self.required_review_roles) != required_roles:
            raise ValueError("Review packet requires clinical, safety, and language review")
        return self

    def content_digest(self) -> str:
        canonical = self.model_dump(
            mode="json",
            exclude={"packet_id", "generated_at"},
        )
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @property
    def clinical_approval_eligible(self) -> bool:
        return not self.placeholder_sources_present and self.validation.passed_cases > 0


class ReviewPacketAttestation(FrozenReviewPacketModel):
    attestation_id: UUID = Field(default_factory=uuid4)
    packet_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    reviewer_id: UUID
    reviewer_role: ReviewerRole
    decision: ReviewDecision
    confirms_expected_results: bool
    confirms_sources_and_sections: bool
    confirms_escalation_wording: bool
    rationale: Annotated[str, Field(min_length=10, max_length=2000)]
    reviewed_at: datetime
    synthetic_rehearsal: bool = True

    @model_validator(mode="after")
    def validate_attestation(self) -> "ReviewPacketAttestation":
        if self.reviewed_at.utcoffset() is None:
            raise ValueError("Review attestation time must include timezone information")
        if self.decision is ReviewDecision.APPROVE and not all(
            (
                self.confirms_expected_results,
                self.confirms_sources_and_sections,
                self.confirms_escalation_wording,
            )
        ):
            raise ValueError("Approval attestation requires all evidence confirmations")
        return self


class ClinicalReviewPacketBuilder:
    def build(
        self,
        candidate: SafetyRuleCandidate,
        dataset: SafetyRuleValidationDataset,
        report: SafetyValidationReport,
        *,
        generated_at: datetime | None = None,
    ) -> SafetyClinicalReviewPacket:
        if report.dataset_version != dataset.dataset_version:
            raise ValueError("Validation report dataset version does not match the dataset")
        if report.ruleset_version != dataset.ruleset_version:
            raise ValueError("Validation report ruleset version does not match the dataset")
        if not report.all_passed:
            raise ValueError("Clinical review packets require a fully passing validation report")

        cases = tuple(case for case in dataset.cases if case.target_rule_id == candidate.rule_id)
        if not cases:
            raise ValueError("Candidate has no validation evidence")
        results = tuple(
            result
            for result in report.results
            if result.target_rule_id == candidate.rule_id
        )
        if len(results) != len(cases) or any(not result.passed for result in results):
            raise ValueError("Candidate validation evidence is incomplete or failing")

        dataset_payload = dataset.model_dump(mode="json")
        dataset_digest = hashlib.sha256(
            json.dumps(dataset_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        categories = tuple(sorted({case.category.value for case in cases}))
        evidence = RuleValidationEvidence(
            rule_id=candidate.rule_id,
            dataset_version=dataset.dataset_version,
            dataset_digest=dataset_digest,
            case_ids=tuple(sorted(case.case_id for case in cases)),
            categories=categories,
            total_cases=len(cases),
            passed_cases=len(results),
        )
        sources = tuple(source.reference for source in candidate.sources)
        return SafetyClinicalReviewPacket(
            packet_version="preclinical-review-2026-08-07.1",
            generated_at=generated_at or datetime.now(UTC),
            candidate_id=candidate.candidate_id,
            rule_id=candidate.rule_id,
            candidate_version=candidate.version,
            candidate_digest=candidate.content_digest(),
            severity=candidate.severity.value,
            predicate_key=candidate.predicate_key,
            clinical_rationale=candidate.clinical_rationale,
            source_references=sources,
            placeholder_sources_present=any(
                source.development_placeholder for source in candidate.sources
            ),
            escalation_wording_version=candidate.escalation_text.wording_version,
            english_escalation_text=candidate.escalation_text.english,
            telugu_escalation_text=candidate.escalation_text.telugu,
            validation=evidence,
            status=ReviewPacketStatus.CLINICAL_INPUT_REQUIRED,
        )
