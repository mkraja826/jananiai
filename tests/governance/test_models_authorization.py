from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from app.auth.models import AuthenticatedUser
from app.governance.authorization import (
    GovernanceAuthorizationError,
    governance_roles_from_user,
    require_governance_roles,
)
from app.governance.models import (
    GovernanceAdminRole,
    ReviewerCredentialReverificationRequest,
    ReviewerOnboardingRequest,
)
from app.safety.governance import ReviewerRole

NOW = datetime(2026, 8, 5, 4, 30, tzinfo=UTC)


def user_with_roles(raw_roles: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(),
        access_token=SecretStr("verified-token"),
        email="admin@example.test",
        app_metadata={"janani_governance_roles": raw_roles},
    )


def onboarding_request(**updates: object) -> ReviewerOnboardingRequest:
    values: dict[str, object] = {
        "reviewer_user_id": uuid4(),
        "display_name": "Synthetic Obstetric Reviewer",
        "reviewer_role": ReviewerRole.OBSTETRICIAN,
        "license_jurisdiction": "IN-test",
        "license_reference": "SYNTHETIC-LICENSE-001",
        "credential_verified_at": NOW,
        "credential_expires_at": NOW + timedelta(days=180),
        "conflict_of_interest_attested": True,
        "conflict_of_interest_attested_at": NOW - timedelta(hours=1),
        "attestation_version": "coi-v1",
        "evidence_reference": "vault://synthetic/reviewer/001",
        "reason": "Synthetic onboarding used only to validate governance controls.",
    }
    values.update(updates)
    return ReviewerOnboardingRequest(**values)


def reverification_request(**updates: object) -> ReviewerCredentialReverificationRequest:
    values: dict[str, object] = {
        "credential_verified_at": NOW,
        "credential_expires_at": NOW + timedelta(days=365),
        "conflict_of_interest_attested": True,
        "conflict_of_interest_attested_at": NOW - timedelta(hours=1),
        "attestation_version": "coi-v2",
        "evidence_reference": "vault://synthetic/reviewer/001/reverification",
        "reason": "Synthetic reverification used only to validate governance controls.",
    }
    values.update(updates)
    return ReviewerCredentialReverificationRequest(**values)


def test_trusted_app_metadata_roles_create_a_principal() -> None:
    user = user_with_roles(
        [
            GovernanceAdminRole.REVIEWER_ADMIN.value,
            GovernanceAdminRole.AUDITOR.value,
            GovernanceAdminRole.REVIEWER_ADMIN.value,
        ]
    )

    principal = require_governance_roles(
        user,
        {GovernanceAdminRole.REVIEWER_ADMIN},
    )

    assert principal.user_id == user.user_id
    assert principal.has_role(GovernanceAdminRole.REVIEWER_ADMIN)
    assert principal.has_role(GovernanceAdminRole.AUDITOR)
    assert user.model_dump() == {
        "user_id": user.user_id,
        "email": "admin@example.test",
        "role": "authenticated",
        "synthetic": False,
    }
    assert "verified-token" not in repr(user)
    assert "janani_governance_roles" not in repr(user)


@pytest.mark.parametrize(
    "raw_roles",
    [
        GovernanceAdminRole.REVIEWER_ADMIN.value,
        [GovernanceAdminRole.REVIEWER_ADMIN.value, 7],
        ["unknown_governance_role"],
    ],
)
def test_malformed_or_unknown_trusted_roles_fail_closed(raw_roles: object) -> None:
    with pytest.raises(GovernanceAuthorizationError):
        governance_roles_from_user(user_with_roles(raw_roles))


def test_missing_role_and_empty_requirement_fail_closed() -> None:
    user = user_with_roles([GovernanceAdminRole.AUDITOR.value])

    with pytest.raises(GovernanceAuthorizationError, match="Missing required"):
        require_governance_roles(user, {GovernanceAdminRole.REVIEWER_ADMIN})
    with pytest.raises(ValueError, match="At least one"):
        require_governance_roles(user, set())


def test_onboarding_and_reverification_accept_complete_evidence() -> None:
    onboarding = onboarding_request()
    reverification = reverification_request()

    assert onboarding.conflict_of_interest_attested
    assert onboarding.reviewer_role is ReviewerRole.OBSTETRICIAN
    assert reverification.credential_expires_at > reverification.credential_verified_at


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"credential_verified_at": datetime(2026, 8, 5, 4, 30)},
            "timestamps must include timezone",
        ),
        (
            {"credential_expires_at": NOW},
            "expiry must follow verification",
        ),
        (
            {"conflict_of_interest_attested": False},
            "attestation is required",
        ),
        (
            {"conflict_of_interest_attested_at": NOW + timedelta(minutes=1)},
            "cannot follow credential verification",
        ),
        (
            {"evidence_reference": "vault://one\nraw-document"},
            "single opaque reference",
        ),
    ],
)
def test_onboarding_evidence_validation_fails_closed(
    updates: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        onboarding_request(**updates)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"credential_expires_at": NOW},
            "expiry must follow verification",
        ),
        (
            {"conflict_of_interest_attested": False},
            "attestation is required",
        ),
        (
            {"conflict_of_interest_attested_at": NOW + timedelta(minutes=1)},
            "cannot follow credential verification",
        ),
        (
            {"evidence_reference": "vault://one\rraw-document"},
            "single opaque reference",
        ),
    ],
)
def test_reverification_evidence_validation_fails_closed(
    updates: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        reverification_request(**updates)
