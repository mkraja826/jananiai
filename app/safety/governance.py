import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.safety.models import (
    RuleMetadata,
    RuleStatus,
    SafetySeverity,
    SymptomAssessmentRequest,
)


class ReviewerRole(StrEnum):
    OBSTETRICIAN = "obstetrician"
    CLINICAL_SAFETY = "clinical_safety"
    LANGUAGE_REVIEWER = "language_reviewer"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class ReleaseStatus(StrEnum):
    APPROVED = "approved"
    ACTIVE = "active"
    EXPIRED = "expired"
    RETIRED = "retired"
    ROLLED_BACK = "rolled_back"


class GovernanceEventType(StrEnum):
    REVIEW_RECORDED = "review_recorded"
    RELEASE_APPROVED = "release_approved"
    RELEASE_ACTIVATED = "release_activated"
    RELEASE_RETIRED = "release_retired"
    RELEASE_ROLLED_BACK = "release_rolled_back"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ClinicalReviewer(FrozenModel):
    reviewer_id: UUID = Field(default_factory=uuid4)
    display_name: Annotated[str, Field(min_length=2, max_length=120)]
    role: ReviewerRole
    license_jurisdiction: Annotated[str, Field(min_length=2, max_length=80)]
    license_reference: Annotated[str, Field(min_length=3, max_length=120)]
    credential_verified_at: datetime
    credential_expires_at: datetime
    active: bool = True

    @model_validator(mode="after")
    def validate_credentials(self) -> "ClinicalReviewer":
        if self.credential_verified_at.utcoffset() is None:
            raise ValueError("Credential verification time must include timezone information")
        if self.credential_expires_at.utcoffset() is None:
            raise ValueError("Credential expiry time must include timezone information")
        if self.credential_expires_at <= self.credential_verified_at:
            raise ValueError("Credential expiry must follow verification")
        return self

    def is_eligible_at(self, checked_at: datetime) -> bool:
        return (
            self.active and self.credential_verified_at <= checked_at < self.credential_expires_at
        )


class ClinicalSource(FrozenModel):
    source_id: Annotated[str, Field(min_length=2, max_length=120)]
    title: Annotated[str, Field(min_length=3, max_length=240)]
    publisher: Annotated[str, Field(min_length=2, max_length=160)]
    reference: Annotated[str, Field(min_length=3, max_length=500)]
    section: Annotated[str, Field(min_length=1, max_length=240)]
    reviewed_at: datetime
    expires_at: datetime
    development_placeholder: bool = False

    @model_validator(mode="after")
    def validate_review_window(self) -> "ClinicalSource":
        if self.reviewed_at.utcoffset() is None or self.expires_at.utcoffset() is None:
            raise ValueError("Source review timestamps must include timezone information")
        if self.expires_at <= self.reviewed_at:
            raise ValueError("Source expiry must follow source review")
        return self

    def is_approval_eligible_at(self, checked_at: datetime) -> bool:
        return not self.development_placeholder and self.reviewed_at <= checked_at < self.expires_at


class RuleApplicability(FrozenModel):
    minimum_gestational_week: Annotated[int | None, Field(ge=0, le=45)] = None
    maximum_gestational_week: Annotated[int | None, Field(ge=0, le=45)] = None
    required_structured_fields: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_boundaries(self) -> "RuleApplicability":
        if (
            self.minimum_gestational_week is not None
            and self.maximum_gestational_week is not None
            and self.minimum_gestational_week > self.maximum_gestational_week
        ):
            raise ValueError("Minimum gestational week cannot exceed maximum week")

        allowed = set(SymptomAssessmentRequest.model_fields) - {"notes", "is_synthetic"}
        unknown = set(self.required_structured_fields) - allowed
        if unknown:
            raise ValueError(f"Unknown structured safety fields: {sorted(unknown)}")
        if len(set(self.required_structured_fields)) != len(self.required_structured_fields):
            raise ValueError("Required structured fields must be unique")
        return self

    def missing_fields(self, payload: SymptomAssessmentRequest) -> tuple[str, ...]:
        return tuple(
            field for field in self.required_structured_fields if getattr(payload, field) is None
        )

    def applies_to(self, payload: SymptomAssessmentRequest) -> bool:
        if self.missing_fields(payload):
            return False
        if self.minimum_gestational_week is not None:
            if payload.gestational_week is None:
                return False
            if payload.gestational_week < self.minimum_gestational_week:
                return False
        if self.maximum_gestational_week is not None:
            if payload.gestational_week is None:
                return False
            if payload.gestational_week > self.maximum_gestational_week:
                return False
        return True


class LocalizedEscalationText(FrozenModel):
    wording_version: Annotated[str, Field(min_length=1, max_length=40)]
    english: Annotated[str, Field(min_length=20, max_length=1000)]
    telugu: Annotated[str, Field(min_length=20, max_length=1000)]


class SafetyRuleCandidate(FrozenModel):
    candidate_id: UUID = Field(default_factory=uuid4)
    rule_id: Annotated[str, Field(min_length=3, max_length=120)]
    version: Annotated[str, Field(min_length=1, max_length=40)]
    status: RuleStatus = RuleStatus.DRAFT
    severity: SafetySeverity
    predicate_key: Annotated[str, Field(min_length=3, max_length=160)]
    clinical_rationale: Annotated[str, Field(min_length=20, max_length=2000)]
    applicability: RuleApplicability
    escalation_text: LocalizedEscalationText
    sources: Annotated[tuple[ClinicalSource, ...], Field(min_length=1)]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    supersedes_version: str | None = None

    @model_validator(mode="after")
    def validate_candidate(self) -> "SafetyRuleCandidate":
        if self.status not in {RuleStatus.DRAFT, RuleStatus.UNDER_REVIEW}:
            raise ValueError("Rule candidates must remain draft or under review")
        if self.created_at.utcoffset() is None:
            raise ValueError("Candidate creation time must include timezone information")
        source_ids = [source.source_id for source in self.sources]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("Candidate source IDs must be unique")
        return self

    def content_digest(self) -> str:
        canonical = self.model_dump(
            mode="json",
            exclude={"candidate_id", "created_at", "status"},
        )
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class ClinicalRuleReview(FrozenModel):
    review_id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    candidate_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    reviewer_id: UUID
    reviewer_role: ReviewerRole
    decision: ReviewDecision
    rationale: Annotated[str, Field(min_length=10, max_length=2000)]
    reviewed_at: datetime

    @model_validator(mode="after")
    def validate_review_time(self) -> "ClinicalRuleReview":
        if self.reviewed_at.utcoffset() is None:
            raise ValueError("Review time must include timezone information")
        return self


class SafetyRuleRelease(FrozenModel):
    release_id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    rule_id: str
    rule_version: str
    candidate_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    approval_review_ids: Annotated[tuple[UUID, ...], Field(min_length=2)]
    reviewer_ids: Annotated[tuple[UUID, ...], Field(min_length=2)]
    reviewer_roles: Annotated[tuple[ReviewerRole, ...], Field(min_length=2)]
    status: ReleaseStatus
    approved_at: datetime
    activates_at: datetime
    expires_at: datetime
    supersedes_release_id: UUID | None = None
    terminal_reason: str | None = None

    @model_validator(mode="after")
    def validate_release(self) -> "SafetyRuleRelease":
        timestamps = (self.approved_at, self.activates_at, self.expires_at)
        if any(item.utcoffset() is None for item in timestamps):
            raise ValueError("Release timestamps must include timezone information")
        if self.activates_at < self.approved_at:
            raise ValueError("Release activation cannot precede approval")
        if self.expires_at <= self.activates_at:
            raise ValueError("Release expiry must follow activation")
        if len(set(self.approval_review_ids)) != len(self.approval_review_ids):
            raise ValueError("Approval review IDs must be unique")
        if len(set(self.reviewer_ids)) != len(self.reviewer_ids):
            raise ValueError("Release requires distinct reviewers")
        return self


class SafetyGovernanceEvent(FrozenModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: GovernanceEventType
    aggregate_id: UUID
    actor_id: UUID | None
    occurred_at: datetime
    reason: Annotated[str, Field(min_length=3, max_length=1000)]
    prior_status: str | None = None
    new_status: str | None = None
    content_digest: Annotated[str | None, Field(pattern=r"^[0-9a-f]{64}$")] = None


class SafetyGovernanceService:
    required_approval_roles = frozenset({ReviewerRole.OBSTETRICIAN, ReviewerRole.CLINICAL_SAFETY})

    def record_review(
        self,
        candidate: SafetyRuleCandidate,
        reviewer: ClinicalReviewer,
        decision: ReviewDecision,
        rationale: str,
        *,
        reviewed_at: datetime | None = None,
    ) -> ClinicalRuleReview:
        checked_at = reviewed_at or datetime.now(UTC)
        if candidate.status not in {RuleStatus.DRAFT, RuleStatus.UNDER_REVIEW}:
            raise ValueError("Only draft or under-review candidates may be reviewed")
        if not reviewer.is_eligible_at(checked_at):
            raise ValueError("Reviewer credentials are not current")
        return ClinicalRuleReview(
            candidate_id=candidate.candidate_id,
            candidate_digest=candidate.content_digest(),
            reviewer_id=reviewer.reviewer_id,
            reviewer_role=reviewer.role,
            decision=decision,
            rationale=rationale,
            reviewed_at=checked_at,
        )

    def approve_release(
        self,
        candidate: SafetyRuleCandidate,
        reviews: tuple[ClinicalRuleReview, ...],
        reviewers: tuple[ClinicalReviewer, ...],
        *,
        approved_at: datetime | None = None,
        activates_at: datetime | None = None,
        expires_at: datetime | None = None,
        supersedes_release_id: UUID | None = None,
    ) -> SafetyRuleRelease:
        checked_at = approved_at or datetime.now(UTC)
        digest = candidate.content_digest()
        reviewer_by_id = {reviewer.reviewer_id: reviewer for reviewer in reviewers}

        if len(reviewer_by_id) != len(reviewers):
            raise ValueError("Reviewer registry contains duplicate identities")
        if any(source.development_placeholder for source in candidate.sources):
            raise ValueError("Development-placeholder sources cannot be clinically approved")
        if any(not source.is_approval_eligible_at(checked_at) for source in candidate.sources):
            raise ValueError("Every clinical source must be current at approval time")
        if not reviews:
            raise ValueError("At least two approvals are required")
        if any(review.candidate_id != candidate.candidate_id for review in reviews):
            raise ValueError("Review candidate IDs do not match")
        if any(review.candidate_digest != digest for review in reviews):
            raise ValueError("A review was recorded against different candidate content")
        if any(review.decision is not ReviewDecision.APPROVE for review in reviews):
            raise ValueError("All release reviews must approve the exact candidate content")

        distinct_reviewers = {review.reviewer_id for review in reviews}
        if len(distinct_reviewers) < 2:
            raise ValueError("Release approval requires two distinct reviewers")
        roles = {review.reviewer_role for review in reviews}
        missing_roles = self.required_approval_roles - roles
        if missing_roles:
            raise ValueError(f"Missing required approval roles: {sorted(missing_roles)}")

        for review in reviews:
            reviewer = reviewer_by_id.get(review.reviewer_id)
            if reviewer is None:
                raise ValueError("Review references an unknown reviewer")
            if reviewer.role is not review.reviewer_role:
                raise ValueError("Review role does not match the reviewer registry")
            if not reviewer.is_eligible_at(checked_at):
                raise ValueError("Every approving reviewer must have current credentials")

        activation_time = activates_at or checked_at
        source_deadline = min(source.expires_at for source in candidate.sources)
        credential_deadline = min(
            reviewer_by_id[reviewer_id].credential_expires_at for reviewer_id in distinct_reviewers
        )
        maximum_expiry = min(source_deadline, credential_deadline)
        requested_expiry = expires_at or min(checked_at + timedelta(days=90), maximum_expiry)
        if requested_expiry > maximum_expiry:
            raise ValueError("Release cannot outlive its clinical sources or reviewer credentials")

        ordered_reviews = tuple(sorted(reviews, key=lambda item: str(item.review_id)))
        return SafetyRuleRelease(
            candidate_id=candidate.candidate_id,
            rule_id=candidate.rule_id,
            rule_version=candidate.version,
            candidate_digest=digest,
            approval_review_ids=tuple(review.review_id for review in ordered_reviews),
            reviewer_ids=tuple(review.reviewer_id for review in ordered_reviews),
            reviewer_roles=tuple(review.reviewer_role for review in ordered_reviews),
            status=ReleaseStatus.APPROVED,
            approved_at=checked_at,
            activates_at=activation_time,
            expires_at=requested_expiry,
            supersedes_release_id=supersedes_release_id,
        )

    def activate_release(
        self,
        release: SafetyRuleRelease,
        *,
        activated_at: datetime | None = None,
    ) -> SafetyRuleRelease:
        checked_at = activated_at or datetime.now(UTC)
        if release.status is not ReleaseStatus.APPROVED:
            raise ValueError("Only approved releases may be activated")
        if checked_at < release.activates_at:
            raise ValueError("Release activation window has not started")
        if checked_at >= release.expires_at:
            raise ValueError("Expired releases cannot be activated")
        return release.model_copy(update={"status": ReleaseStatus.ACTIVE})

    def retire_release(
        self,
        release: SafetyRuleRelease,
        reason: str,
    ) -> SafetyRuleRelease:
        if release.status not in {ReleaseStatus.APPROVED, ReleaseStatus.ACTIVE}:
            raise ValueError("Only approved or active releases may be retired")
        return release.model_copy(
            update={"status": ReleaseStatus.RETIRED, "terminal_reason": reason}
        )

    def rollback_release(
        self,
        active_release: SafetyRuleRelease,
        replacement_release: SafetyRuleRelease,
        reason: str,
        *,
        rolled_back_at: datetime | None = None,
    ) -> tuple[SafetyRuleRelease, SafetyRuleRelease]:
        checked_at = rolled_back_at or datetime.now(UTC)
        if active_release.status is not ReleaseStatus.ACTIVE:
            raise ValueError("Only an active release may be rolled back")
        if replacement_release.rule_id != active_release.rule_id:
            raise ValueError("Rollback replacement must belong to the same rule")
        if replacement_release.status not in {
            ReleaseStatus.APPROVED,
            ReleaseStatus.RETIRED,
        }:
            raise ValueError("Rollback replacement must be an approved prior release")
        if checked_at >= replacement_release.expires_at:
            raise ValueError("Rollback replacement has expired")

        rolled_back = active_release.model_copy(
            update={"status": ReleaseStatus.ROLLED_BACK, "terminal_reason": reason}
        )
        replacement = replacement_release.model_copy(
            update={"status": ReleaseStatus.ACTIVE, "terminal_reason": None}
        )
        return rolled_back, replacement

    def build_approved_metadata(
        self,
        candidate: SafetyRuleCandidate,
        release: SafetyRuleRelease,
        *,
        checked_at: datetime | None = None,
    ) -> RuleMetadata:
        now = checked_at or datetime.now(UTC)
        if release.status is not ReleaseStatus.ACTIVE:
            raise ValueError("Only an active governance release can create engine metadata")
        if release.candidate_id != candidate.candidate_id:
            raise ValueError("Release and candidate identities do not match")
        if release.candidate_digest != candidate.content_digest():
            raise ValueError("Release digest no longer matches candidate content")
        if not (release.activates_at <= now < release.expires_at):
            raise ValueError("Release is outside its activation window")

        return RuleMetadata(
            rule_id=candidate.rule_id,
            version=candidate.version,
            status=RuleStatus.APPROVED,
            severity=candidate.severity,
            response_template=candidate.escalation_text.english,
            clinician_signoff_ids=tuple(str(item) for item in release.reviewer_ids),
            governance_release_id=str(release.release_id),
            governance_content_digest=release.candidate_digest,
            approved_at=release.approved_at,
            next_review_at=release.expires_at,
        )
