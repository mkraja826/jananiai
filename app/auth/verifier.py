from uuid import UUID

import httpx
from pydantic import SecretStr, ValidationError

from app.auth.models import AuthenticatedUser


class AuthenticationError(Exception):
    """Raised when a bearer token is missing, invalid, or expired."""


class AuthenticationServiceUnavailable(Exception):
    """Raised when Supabase Auth cannot validate a token reliably."""


class SupabaseAuthVerifier:
    """Validates access tokens with Supabase Auth's user endpoint."""

    def __init__(
        self,
        *,
        supabase_url: str,
        publishable_key: str,
        timeout_seconds: float = 8.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._supabase_url = supabase_url.rstrip("/")
        self._publishable_key = publishable_key
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def verify(self, access_token: str) -> AuthenticatedUser:
        try:
            response = await self._client.get(
                f"{self._supabase_url}/auth/v1/user",
                headers={
                    "apikey": self._publishable_key,
                    "Authorization": f"Bearer {access_token}",
                },
            )
        except httpx.RequestError as exc:
            raise AuthenticationServiceUnavailable("Supabase Auth could not be reached") from exc

        if response.status_code in {401, 403}:
            raise AuthenticationError("Bearer token is invalid or expired")
        if response.status_code >= 500:
            raise AuthenticationServiceUnavailable(
                "Supabase Auth could not validate the bearer token"
            )
        if response.status_code != 200:
            raise AuthenticationError("Bearer token validation failed")

        try:
            payload = response.json()
            app_metadata = payload.get("app_metadata") or {}
            if not isinstance(app_metadata, dict):
                raise TypeError("app_metadata must be an object")
            return AuthenticatedUser(
                user_id=UUID(payload["id"]),
                access_token=SecretStr(access_token),
                email=payload.get("email"),
                role=payload.get("role") or "authenticated",
                app_metadata=app_metadata,
                synthetic=False,
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise AuthenticationServiceUnavailable(
                "Supabase Auth returned an invalid user response"
            ) from exc
