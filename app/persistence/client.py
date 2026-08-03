from collections.abc import Mapping
from typing import Any

import httpx

from app.auth.models import AuthenticatedUser


class SupabasePersistenceError(Exception):
    """Raised when a PostgREST or RPC request cannot be completed safely."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class SupabaseUserRestClient:
    """RLS-scoped Supabase REST client using the caller's verified access token."""

    def __init__(
        self,
        *,
        supabase_url: str,
        publishable_key: str,
        user: AuthenticatedUser,
        timeout_seconds: float = 8.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = supabase_url.rstrip("/")
        self._publishable_key = publishable_key
        self._user = user
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    @property
    def user(self) -> AuthenticatedUser:
        return self._user

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._publishable_key,
            "Authorization": f"Bearer {self._user.bearer_token}",
            "Accept-Profile": "public",
            "Content-Profile": "public",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    async def select(
        self,
        table: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        response = await self._request(
            "GET",
            f"/rest/v1/{table}",
            params=params,
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise SupabasePersistenceError("Supabase returned a non-list select response")
        return payload

    async def insert(
        self,
        table: str,
        payload: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        response = await self._request(
            "POST",
            f"/rest/v1/{table}",
            json=dict(payload),
            prefer="return=representation",
        )
        data = response.json()
        if not isinstance(data, list):
            raise SupabasePersistenceError("Supabase returned a non-list insert response")
        return data

    async def rpc(
        self,
        function_name: str,
        payload: Mapping[str, Any],
    ) -> Any:
        response = await self._request(
            "POST",
            f"/rest/v1/rpc/{function_name}",
            json=dict(payload),
        )
        if not response.content:
            return None
        return response.json()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
        prefer: str | None = None,
    ) -> httpx.Response:
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                params=params,
                json=json,
                headers=self._headers(prefer=prefer),
            )
        except httpx.RequestError as exc:
            raise SupabasePersistenceError("Supabase data service could not be reached") from exc

        if response.status_code in {401, 403}:
            raise SupabasePersistenceError(
                "Supabase RLS denied the requested operation",
                status_code=403,
            )
        if response.status_code >= 400:
            raise SupabasePersistenceError(
                f"Supabase data request failed with status {response.status_code}",
                status_code=502,
            )
        return response
