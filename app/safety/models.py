from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class RuleStatus(StrEnum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    RETIRED = "retired"


class SafetySeverity(StrEnum):
    ROUTINE = "routine"
    CONTACT_CLINICIAN = "contact_clinician"
    URGENT = "urgent"
    EMERGENCY = "emergency"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class RuleMetadata(BaseModel):
    rule_id: str
    version: str
    status: RuleStatus
    severity: SafetySeverity
    response_template: str
    clinician_signoff_ids: tuple[str, ...] = ()
    governance_release_id: str | None = None
    governance_content_digest: Annotated[
        str | None,
        Field(pattern=r"^[0-9a-f]{64}$"),
    ] = None
    approved_at: datetime | None = None
    next_review_at: datetime | None = None

    @model_validator(mode="after")
    def validate_approval_metadata(self) -> "RuleMetadata":
        if self.status is not RuleStatus.APPROVED:
            return self

        signoff_ids = {item.strip() for item in self.clinician_signoff_ids if item.strip()}
        if len(signoff_ids) < 2:
            raise ValueError("Approved rules require two distinct clinician sign-offs")
        if not self.governance_release_id or not self.governance_content_digest:
            raise ValueError("Approved rules require a governance release ID and content digest")
        if not self.approved_at or not self.next_review_at:
            raise ValueError("Approved rules require approval and next-review times")
        if self.approved_at.utcoffset() is None or self.next_review_at.utcoffset() is None:
            raise ValueError("Approved rule timestamps must include timezone information")
        if self.next_review_at <= self.approved_at:
            raise ValueError("Rule review time must be later than its approval time")
        return self

    def is_clinically_approved_at(self, checked_at: datetime) -> bool:
        signoff_ids = {item.strip() for item in self.clinician_signoff_ids if item.strip()}
        return (
            self.status is RuleStatus.APPROVED
            and len(signoff_ids) >= 2
            and bool(self.governance_release_id)
            and bool(self.governance_content_digest)
            and self.approved_at is not None
            and self.next_review_at is not None
            and self.approved_at <= checked_at < self.next_review_at
        )

    @property
    def is_clinically_approved(self) -> bool:
        return self.is_clinically_approved_at(datetime.now(UTC))


class SymptomAssessmentRequest(BaseModel):
    """Structured inputs only; free text is never used for deterministic decisions."""

    is_synthetic: bool = True
    gestational_week: Annotated[int | None, Field(ge=0, le=45)] = None
    heavy_bleeding: bool = False
    severe_abdominal_pain: bool = False
    reduced_fetal_movement: bool = False
    severe_headache: bool = False
    vision_changes: bool = False
    seizure: bool = False
    loss_of_consciousness: bool = False
    severe_breathing_difficulty: bool = False
    notes: Annotated[str | None, Field(max_length=500)] = None


class SafetyDecision(BaseModel):
    event_id: UUID
    triggered: bool
    severity: SafetySeverity
    triggered_rule_ids: list[str]
    message: str
    blocks_llm: bool
    ruleset_version: str
    ruleset_clinically_approved: bool
    development_only: bool
    disclaimer: str


class ReadinessResponse(BaseModel):
    service_ready: bool
    clinical_ready: bool
    synthetic_data_only: bool
    llm_provider: str
    reasons: list[str]
