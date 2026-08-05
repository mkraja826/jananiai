from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.auth.dependencies import get_current_user
from app.auth.models import AuthenticatedUser
from app.config import Settings
from app.governance.dependencies import get_governance_admin_repository
from app.governance.models import (
    GovernanceAdminRole,
    GovernancePrincipal,
    ReviewerAdministrationResult,
    ReviewerCredentialReverificationRequest,
    ReviewerDeactivationRequest,
    ReviewerOnboardingRequest,
)
from app.governance.repository import GovernanceAdministrationError
from app.main import create_app

NOW = datetime(2026, 8, 5, 5, 30, tzinfo=UTC)
REVIEWER_ID = UUID("10000000-0000-0000-0000-000000000001")


class FakeGovernanceRepository:
    def __init__(self, error: GovernanceAdministrationError | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, UUID, UUID | None]] = []

    async def onboard_reviewer(
        self,
        principal: GovernancePrincipal,
        request: ReviewerOnboardingRequest,
    ) -> ReviewerAdministrationResult:
        if self.error:
            raise self.error
        self.calls.append(("onboard", principal.user_id, request.reviewer_user_id))
        return ReviewerAdministrationResult(
            reviewer_id=REVIEWER_ID,
            active=True,
            action="onboarded",
        )

    async def reverify_reviewer(
        self,
        principal: GovernancePrincipal,
        reviewer_id: UUID,
        request: ReviewerCredentialReverificationRequest,
    ) -> ReviewerAdministrationResult:
        if self.error:
            raise self.error
        self.calls.append(("reverify", principal.user_id, reviewer_id))
        assert request.attestation_version == "coi-v2"
        return ReviewerAdministrationResult(
            reviewer_id=reviewer_id,
            active=True,
            action="reverified",
        )

    async def deactivate_reviewer(
        self,
        principal: GovernancePrincipal,
        reviewer_id: UUID,
        request: ReviewerDeactivationRequest,
    ) -> ReviewerAdministrationResult:
        if self.error:
            raise self.error
        self.calls.append(("deactivate", principal.user_id, reviewer_id))
        assert "Synthetic" in request.reason
        return ReviewerAdministrationResult(
            reviewer_id=reviewer_id,
            active=False,
            action="deactivated",
        )


def admin_settings(*, enabled: bool = True) -> Settings:
    return Settings(
        environment="test",
        auth_required=enabled,
        supabase_url="https://synthetic-project.supabase.co" if enabled else None,
        supabase_publishable_key="synthetic-publishable" if enabled else None,
        supabase_service_role_key="synthetic-service-role" if enabled else None,
        governance_admin_api_enabled=enabled,
    )


def verified_user(*roles: GovernanceAdminRole) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=UUID("20000000-0000-0000-0000-000000000001"),
        access_token=SecretStr("verified-admin-token"),
        email="admin@example.test",
        app_metadata={"janani_governance_roles": [role.value for role in roles]},
    )


def onboarding_payload() -> dict[str, object]:
    return {
        "reviewer_user_id": str(uuid4()),
        "display_name": "Synthetic Obstetric Reviewer",
        "reviewer_role": "obstetrician",
        "license_jurisdiction": "IN-test",
        "license_reference": f"SYNTHETIC-{uuid4()}",
        "credential_verified_at": NOW.isoformat(),
        "credential_expires_at": (NOW + timedelta(days=180)).isoformat(),
        "conflict_of_interest_attested": True,
        "conflict_of_interest_attested_at": (NOW - timedelta(hours=1)).isoformat(),
        "attestation_version": "coi-v1",
        "evidence_reference": "vault://synthetic/reviewer/api",
        "reason": "Synthetic reviewer onboarding validates the protected HTTP boundary.",
    }


def test_governance_routes_are_hidden_when_disabled() -> None:
    client = TestClient(create_app(settings=admin_settings(enabled=False)))

    response = client.post("/v1/governance/reviewers", json=onboarding_payload())

    assert response.status_code == 404
    assert response.json()["detail"] == "Governance administration API is disabled"


def test_governance_routes_require_trusted_reviewer_admin_role() -> None:
    app = create_app(settings=admin_settings())
    repository = FakeGovernanceRepository()
    app.dependency_overrides[get_current_user] = lambda: verified_user(GovernanceAdminRole.AUDITOR)
    app.dependency_overrides[get_governance_admin_repository] = lambda: repository
    client = TestClient(app)

    response = client.post("/v1/governance/reviewers", json=onboarding_payload())

    assert response.status_code == 403
    assert "reviewer_admin" in response.json()["detail"]
    assert repository.calls == []


def test_reviewer_admin_can_onboard_reverify_and_deactivate() -> None:
    app = create_app(settings=admin_settings())
    repository = FakeGovernanceRepository()
    admin = verified_user(GovernanceAdminRole.REVIEWER_ADMIN, GovernanceAdminRole.AUDITOR)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_governance_admin_repository] = lambda: repository
    client = TestClient(app)

    onboard = client.post("/v1/governance/reviewers", json=onboarding_payload())
    reverify = client.post(
        f"/v1/governance/reviewers/{REVIEWER_ID}/reverify",
        json={
            "credential_verified_at": NOW.isoformat(),
            "credential_expires_at": (NOW + timedelta(days=365)).isoformat(),
            "conflict_of_interest_attested": True,
            "conflict_of_interest_attested_at": (NOW - timedelta(hours=1)).isoformat(),
            "attestation_version": "coi-v2",
            "evidence_reference": "vault://synthetic/reviewer/api/v2",
            "reason": "Synthetic credential reverification validates the protected HTTP boundary.",
        },
    )
    deactivate = client.post(
        f"/v1/governance/reviewers/{REVIEWER_ID}/deactivate",
        json={"reason": "Synthetic reviewer deactivation validates the protected HTTP boundary."},
    )

    assert onboard.status_code == 201
    assert onboard.json() == {
        "reviewer_id": str(REVIEWER_ID),
        "active": True,
        "action": "onboarded",
    }
    assert reverify.status_code == 200
    assert reverify.json()["action"] == "reverified"
    assert deactivate.status_code == 200
    assert deactivate.json() == {
        "reviewer_id": str(REVIEWER_ID),
        "active": False,
        "action": "deactivated",
    }
    assert [call[0] for call in repository.calls] == [
        "onboard",
        "reverify",
        "deactivate",
    ]
    assert {call[1] for call in repository.calls} == {admin.user_id}


def test_governance_repository_errors_are_safely_mapped() -> None:
    app = create_app(settings=admin_settings())
    repository = FakeGovernanceRepository(
        GovernanceAdministrationError(
            "Governance operation conflicts with an existing record",
            status_code=409,
        )
    )
    app.dependency_overrides[get_current_user] = lambda: verified_user(
        GovernanceAdminRole.REVIEWER_ADMIN
    )
    app.dependency_overrides[get_governance_admin_repository] = lambda: repository
    client = TestClient(app)

    response = client.post("/v1/governance/reviewers", json=onboarding_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == ("Governance operation conflicts with an existing record")
