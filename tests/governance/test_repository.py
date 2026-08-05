import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest

from app.governance.models import (
    GovernanceAdminRole,
    GovernancePrincipal,
    ReviewerCredentialReverificationRequest,
    ReviewerDeactivationRequest,
    ReviewerOnboardingRequest,
)
from app.governance.repository import (
    GovernanceAdministrationError,
    SupabaseGovernanceAdminRepository,
)
from app.safety.governance import ReviewerRole

NOW = datetime(2026, 8, 5, 5, 0, tzinfo=UTC)
SERVICE_KEY = "synthetic-service-role-key"


def principal() -> GovernancePrincipal:
    return GovernancePrincipal(
        user_id=uuid4(),
        email="admin@example.test",
        roles=frozenset({GovernanceAdminRole.REVIEWER_ADMIN}),
    )


def onboarding_request() -> ReviewerOnboardingRequest:
    return ReviewerOnboardingRequest(
        reviewer_user_id=uuid4(),
        display_name="Synthetic Safety Reviewer",
        reviewer_role=ReviewerRole.CLINICAL_SAFETY,
        license_jurisdiction="IN-test",
        license_reference="SYNTHETIC-SAFETY-001",
        credential_verified_at=NOW,
        credential_expires_at=NOW + timedelta(days=180),
        conflict_of_interest_attested=True,
        conflict_of_interest_attested_at=NOW - timedelta(hours=1),
        attestation_version="coi-v1",
        evidence_reference="vault://synthetic/safety/001",
        reason="Synthetic reviewer onboarding for repository contract validation.",
    )


def reverification_request() -> ReviewerCredentialReverificationRequest:
    return ReviewerCredentialReverificationRequest(
        credential_verified_at=NOW + timedelta(days=1),
        credential_expires_at=NOW + timedelta(days=365),
        conflict_of_interest_attested=True,
        conflict_of_interest_attested_at=NOW,
        attestation_version="coi-v2",
        evidence_reference="vault://synthetic/safety/001/reverified",
        reason="Synthetic credential reverification for repository contract validation.",
    )


def test_repository_uses_service_role_only_and_maps_all_actions() -> None:
    reviewer_id = uuid4()
    actor = principal()
    onboarding = onboarding_request()
    captured: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        captured.append((request.url.path, payload, dict(request.headers)))
        return httpx.Response(200, json=str(reviewer_id))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    repository = SupabaseGovernanceAdminRepository(
        supabase_url="https://example.supabase.co/",
        service_role_key=SERVICE_KEY,
        client=client,
    )

    async def exercise() -> None:
        onboarded = await repository.onboard_reviewer(actor, onboarding)
        reverified = await repository.reverify_reviewer(
            actor,
            reviewer_id,
            reverification_request(),
        )
        deactivated = await repository.deactivate_reviewer(
            actor,
            reviewer_id,
            ReviewerDeactivationRequest(
                reason="Synthetic reviewer deactivation after validation completion."
            ),
        )
        await client.aclose()

        assert onboarded.action == "onboarded" and onboarded.active
        assert reverified.action == "reverified" and reverified.active
        assert deactivated.action == "deactivated" and not deactivated.active
        assert {onboarded.reviewer_id, reverified.reviewer_id, deactivated.reviewer_id} == {
            reviewer_id
        }

    asyncio.run(exercise())

    assert [item[0] for item in captured] == [
        "/rest/v1/rpc/onboard_janani_clinical_reviewer",
        "/rest/v1/rpc/reverify_janani_clinical_reviewer",
        "/rest/v1/rpc/deactivate_janani_clinical_reviewer",
    ]
    for _, payload, headers in captured:
        assert headers["apikey"] == SERVICE_KEY
        assert headers["authorization"] == f"Bearer {SERVICE_KEY}"
        assert payload["p_actor_user_id"] == str(actor.user_id)
        assert "verified-token" not in json.dumps(payload)
    assert captured[0][1]["p_role"] == ReviewerRole.CLINICAL_SAFETY.value
    assert captured[0][1]["p_reviewer_user_id"] == str(onboarding.reviewer_user_id)
    assert captured[1][1]["p_reviewer_id"] == str(reviewer_id)
    assert captured[2][1]["p_reviewer_id"] == str(reviewer_id)


def test_repository_accepts_unbound_reviewer_identity() -> None:
    reviewer_id = uuid4()
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content.decode()))
        return httpx.Response(200, json=str(reviewer_id))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    repository = SupabaseGovernanceAdminRepository(
        supabase_url="https://example.supabase.co",
        service_role_key=SERVICE_KEY,
        client=client,
    )
    request = onboarding_request().model_copy(update={"reviewer_user_id": None})

    async def exercise() -> None:
        result = await repository.onboard_reviewer(principal(), request)
        await client.aclose()
        assert result.reviewer_id == reviewer_id

    asyncio.run(exercise())
    assert captured_payload["p_reviewer_user_id"] is None


@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [
        (401, 403),
        (403, 403),
        (404, 404),
        (409, 409),
        (422, 400),
        (500, 502),
    ],
)
def test_repository_maps_postgrest_failures(
    status_code: int,
    expected_status: int,
) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status_code, json={"message": "synthetic"})
        )
    )
    repository = SupabaseGovernanceAdminRepository(
        supabase_url="https://example.supabase.co",
        service_role_key=SERVICE_KEY,
        client=client,
    )

    async def exercise() -> None:
        with pytest.raises(GovernanceAdministrationError) as exc_info:
            await repository.deactivate_reviewer(
                principal(),
                uuid4(),
                ReviewerDeactivationRequest(
                    reason="Synthetic deactivation expected to fail for mapping validation."
                ),
            )
        await client.aclose()
        assert exc_info.value.status_code == expected_status

    asyncio.run(exercise())


def test_repository_rejects_invalid_rpc_response_and_transport_failure() -> None:
    invalid_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json="not-a-uuid"))
    )
    invalid_repository = SupabaseGovernanceAdminRepository(
        supabase_url="https://example.supabase.co",
        service_role_key=SERVICE_KEY,
        client=invalid_client,
    )

    def broken_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic connection failure", request=request)

    broken_client = httpx.AsyncClient(transport=httpx.MockTransport(broken_handler))
    broken_repository = SupabaseGovernanceAdminRepository(
        supabase_url="https://example.supabase.co",
        service_role_key=SERVICE_KEY,
        client=broken_client,
    )

    async def exercise() -> None:
        with pytest.raises(GovernanceAdministrationError, match="invalid response"):
            await invalid_repository.deactivate_reviewer(
                principal(),
                UUID("00000000-0000-0000-0000-000000000001"),
                ReviewerDeactivationRequest(
                    reason="Synthetic invalid response validation for repository safety."
                ),
            )
        with pytest.raises(GovernanceAdministrationError, match="could not be reached"):
            await broken_repository.deactivate_reviewer(
                principal(),
                UUID("00000000-0000-0000-0000-000000000002"),
                ReviewerDeactivationRequest(
                    reason="Synthetic transport failure validation for repository safety."
                ),
            )
        await invalid_client.aclose()
        await broken_client.aclose()

    asyncio.run(exercise())


def test_repository_requires_nonempty_service_role_key() -> None:
    with pytest.raises(ValueError, match="Service-role key is required"):
        SupabaseGovernanceAdminRepository(
            supabase_url="https://example.supabase.co",
            service_role_key="   ",
        )
