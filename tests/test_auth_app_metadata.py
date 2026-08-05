import asyncio
from uuid import UUID

import httpx
import pytest

from app.auth.verifier import AuthenticationServiceUnavailable, SupabaseAuthVerifier

USER_ID = UUID("30000000-0000-0000-0000-000000000001")


def test_auth_verifier_loads_server_controlled_app_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "synthetic-publishable"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        return httpx.Response(
            200,
            json={
                "id": str(USER_ID),
                "email": "admin@example.test",
                "role": "authenticated",
                "app_metadata": {
                    "janani_governance_roles": ["reviewer_admin", "auditor"]
                },
                "user_metadata": {"janani_governance_roles": ["safety_release_manager"]},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    verifier = SupabaseAuthVerifier(
        supabase_url="https://synthetic-project.supabase.co",
        publishable_key="synthetic-publishable",
        client=client,
    )

    async def exercise() -> None:
        user = await verifier.verify("synthetic-token")
        await client.aclose()

        assert user.user_id == USER_ID
        assert user.app_metadata == {
            "janani_governance_roles": ["reviewer_admin", "auditor"]
        }
        assert "safety_release_manager" not in str(user.app_metadata)
        assert "synthetic-token" not in repr(user)
        assert "janani_governance_roles" not in repr(user)

    asyncio.run(exercise())


@pytest.mark.parametrize("app_metadata", ["reviewer_admin", ["reviewer_admin"]])
def test_auth_verifier_rejects_non_object_app_metadata(app_metadata: object) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "id": str(USER_ID),
                    "app_metadata": app_metadata,
                },
            )
        )
    )
    verifier = SupabaseAuthVerifier(
        supabase_url="https://synthetic-project.supabase.co",
        publishable_key="synthetic-publishable",
        client=client,
    )

    async def exercise() -> None:
        with pytest.raises(AuthenticationServiceUnavailable, match="invalid user response"):
            await verifier.verify("synthetic-token")
        await client.aclose()

    asyncio.run(exercise())
