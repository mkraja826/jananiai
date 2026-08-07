from uuid import UUID

import httpx

from app.notifications.models import (
    NotificationDestination,
    NotificationPlatform,
    NotificationTransportKind,
)


class NotificationWorkerError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class SupabaseNotificationWorkerRepository:
    """Service-role-only destination lookup tied to an exact active reminder claim."""

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        timeout_seconds: float = 8.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not service_role_key.strip():
            raise ValueError("Service-role key is required")
        self._supabase_url = supabase_url.rstrip("/")
        self._service_role_key = service_role_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def destinations_for_claim(
        self,
        *,
        delivery_id: UUID,
        claim_token: UUID,
    ) -> list[NotificationDestination]:
        payload = await self._rpc(
            "get_janani_notification_destinations",
            {
                "p_delivery_id": str(delivery_id),
                "p_claim_token": str(claim_token),
            },
        )
        if not isinstance(payload, list):
            raise NotificationWorkerError("Notification destination RPC returned an invalid list")
        return [self._map_destination(row) for row in payload]

    async def _rpc(self, function_name: str, payload: dict[str, object]) -> object:
        try:
            response = await self._client.post(
                f"{self._supabase_url}/rest/v1/rpc/{function_name}",
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                    "Content-Type": "application/json",
                    "Accept-Profile": "public",
                    "Content-Profile": "public",
                },
                json=payload,
            )
        except httpx.RequestError as exc:
            raise NotificationWorkerError(
                "Notification destination persistence could not be reached"
            ) from exc

        if response.status_code in {401, 403}:
            raise NotificationWorkerError(
                "Notification worker operation was denied",
                status_code=403,
            )
        if response.status_code == 404:
            raise NotificationWorkerError("Notification worker RPC was not found", status_code=404)
        if response.status_code >= 500:
            raise NotificationWorkerError("Notification destination persistence failed")
        if response.status_code >= 400:
            raise NotificationWorkerError(
                "Notification worker operation was rejected",
                status_code=400,
            )
        if not response.content:
            return None
        return response.json()

    def _map_destination(self, row: object) -> NotificationDestination:
        if not isinstance(row, dict):
            raise NotificationWorkerError("Notification destination row is invalid")
        return NotificationDestination(
            device_id=UUID(row["id"]),
            platform=NotificationPlatform(row["platform"]),
            transport=NotificationTransportKind(row["transport"]),
            push_token=row["push_token"],
            synthetic=bool(row.get("synthetic", True)),
        )
