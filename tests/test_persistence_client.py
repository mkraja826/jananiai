import asyncio
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from app.auth.models import AuthenticatedUser
from app.persistence.client import SupabasePersistenceError, SupabaseUserRestClient


def user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=UUID("00000000-0000-0000-0000-000000000333"),
        access_token=SecretStr("synthetic-user-token"),
    )


def test_user_rest_client_propagates_verified_token_and_publishable_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer synthetic-user-token"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        assert request.url.path == "/rest/v1/pregnancies"
        return httpx.Response(200, json=[])

    client = SupabaseUserRestClient(
        supabase_url="https://synthetic-project.supabase.co",
        publishable_key="sb_publishable_synthetic",
        user=user(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    rows = asyncio.run(client.select("pregnancies", params={"select": "*"}))

    assert rows == []


def test_user_rest_client_surfaces_rls_denial_without_response_body() -> None:
    client = SupabaseUserRestClient(
        supabase_url="https://synthetic-project.supabase.co",
        publishable_key="sb_publishable_synthetic",
        user=user(),
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(403))
        ),
    )

    with pytest.raises(SupabasePersistenceError) as error:
        asyncio.run(client.select("pregnancies"))

    assert error.value.status_code == 403
    assert "RLS denied" in str(error.value)
