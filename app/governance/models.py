from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.safety.governance import ReviewerRole


class GovernanceAdminRole(StrEnum):
    REVIEWER_ADMIN = "reviewer_admin"
    SAFETY_RELEASE_MANAGER = "safety_release_manager"
    AUDITOR = "auditor"


class FrozenGovernanceModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GovernancePrincipal(FrozenGovernanceModel):
    user_id: UUID
    email: str | None = None
    roles: frozenset[GovernanceAdminRole]

    def has_role(self, role: GovernanceAdminRole) -> bool:
        return role in self.roles


class ReviewerOnboardingRequest(FrozenGovernanceModel):
    reviewer_user_id: UUID | None = None
    display_name: Annotated[str, Field(min_length=2, max_length=120)]
    reviewer_role: ReviewerRole
    license_jurisdiction: Annotated[str, Field(min_length=2, max_length=80)]
    license_reference: Annotated[str, Field(min_length=3, max_length=120)]
    credential_verified_at: datetime
    credential_expires_at: datetime
    conflict_of_interest_attested: bool
    conflict_of_interest_attested_at: datetime
    attestation_version: Annotated[str, Field(min_length=3, max_length=80)]
    evidence_reference: Annotated[str, Field(min_length=3, max_length=500)]
    reason: Annotated[str, Field(min_length=20, max_length=1000)]

    @model_validator(mode="after")
    def validate_onboarding(self) -> "ReviewerOnboardingRequest":
        timestamps = (
            self.credential_verified_at,
            self.credential_expires_at,
            self.conflict_of_interest_attested_at,
        )
        if any(item.utcoffset() is None for item in timestamps):
            raise ValueError("Reviewer onboarding timestamps must include timezone information")
        if self.credential_expires_at <= self.credential_verified_at:
            raise ValueError("Reviewer credential expiry must follow verification")
        if not self.conflict_of_interest_attested:
            raise ValueError("Conflict-of-interest attestation is required")
        if self.conflict_of_interest_attested_at > self.credential_verified_at:
            raise ValueError(
                "Conflict-of-interest attestation cannot follow credential verification"
            )
        if "\n" in self.evidence_reference or "\r" in self.evidence_reference:
            raise ValueError("Evidence reference must be a single opaque reference")
        return self


class ReviewerCredentialReverificationRequest(FrozenGovernanceModel):
    credential_verified_at: datetime
    credential_expires_at: datetime
    conflict_of_interest_attested: bool
    conflict_of_interest_attested_at: datetime
    attestation_version: Annotated[str, Field(min_length=3, max_length=80)]
    evidence_reference: Annotated[str, Field(min_length=3, max_length=500)]
    reason: Annotated[str, Field(min_length=20, max_length=1000)]

    @model_validator(mode="after")
    def validate_reverification(self) -> "ReviewerCredentialReverificationRequest":
        timestamps = (
            self.credential_verified_at,
            self.credential_expires_at,
            self.conflict_of_interest_attested_at,
        )
        if any(item.utcoffset() is None for item in timestamps):
            raise ValueError("Reviewer reverification timestamps must include timezone information")
        if self.credential_expires_at <= self.credential_verified_at:
            raise ValueError("Reviewer credential expiry must follow verification")
        if not self.conflict_of_interest_attested:
            raise ValueError("Conflict-of-interest attestation is required")
        if self.conflict_of_interest_attested_at > self.credential_verified_at:
            raise ValueError(
                "Conflict-of-interest attestation cannot follow credential verification"
            )
        if "\n" in self.evidence_reference or "\r" in self.evidence_reference:
            raise ValueError("Evidence reference must be a single opaque reference")
        return self


class ReviewerDeactivationRequest(FrozenGovernanceModel):
    reason: Annotated[str, Field(min_length=20, max_length=1000)]


class ReviewerAdministrationResult(FrozenGovernanceModel):
    reviewer_id: UUID
    active: bool
    action: Annotated[str, Field(pattern=r"^(onboarded|reverified|deactivated)$")]
