import asyncio
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from app.auth.models import AuthenticatedUser
from app.auth.verifier import (
    AuthenticationError,
    AuthenticationServiceUnavailable,
    SupabaseAuthVerifier,
)


def verifier_with(handler) -> SupabaseAuthVerifier:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return SupabaseAuthVerifier(
        supabase_url="https://synthetic-project.supabase.co",
        publishable_key="sb_publishable_synthetic",
        client=client,
    )


def test_auth_model_never_serializes_bearer_token() -> None:
    user = AuthenticatedUser(
        user_id=UUID("00000000-0000-0000-0000-000000000111"),
        access_token=SecretStr("synthetic-secret-token"),
    )

    assert "access_token" not in user.model_dump()
    assert "synthetic-secret-token" not in repr(user)


def test_supabase_auth_verifier_returns_verified_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        assert request.headers["authorization"] == "Bearer synthetic-access-token"
        return httpx.Response(
            200,
            json={
                "id": "00000000-0000-0000-0000-000000000222",
                "email": "synthetic@example.invalid",
                "role": "authenticated",
            },
        )

    user = asyncio.run(verifier_with(handler).verify("synthetic-access-token"))

    assert user.user_id == UUID("00000000-0000-0000-0000-000000000222")
    assert user.synthetic is False
    assert user.bearer_token == "synthetic-access-token"


def test_supabase_auth_verifier_rejects_invalid_token() -> None:
    verifier = verifier_with(lambda request: httpx.Response(401, json={"message": "invalid"}))

    with pytest.raises(AuthenticationError, match="invalid or expired"):
        asyncio.run(verifier.verify("invalid-token"))


def test_supabase_auth_verifier_fails_closed_on_server_error() -> None:
    verifier = verifier_with(lambda request: httpx.Response(503, json={"message": "down"}))

    with pytest.raises(AuthenticationServiceUnavailable):
        asyncio.run(verifier.verify("synthetic-token"))
