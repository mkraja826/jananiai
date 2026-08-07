from typing import Protocol
from uuid import UUID

from app.auth.models import AuthenticatedUser
from app.notifications.models import (
    NotificationDevice,
    NotificationDeviceOverview,
    NotificationDeviceRegistrationRequest,
    NotificationPlatform,
    NotificationTransportKind,
)
from app.persistence.client import SupabasePersistenceError, SupabaseUserRestClient


class NotificationDeviceRepository(Protocol):
    async def list_devices(self, user: AuthenticatedUser) -> NotificationDeviceOverview: ...

    async def register_device(
        self,
        user: AuthenticatedUser,
        payload: NotificationDeviceRegistrationRequest,
    ) -> NotificationDevice: ...

    async def revoke_device(
        self,
        user: AuthenticatedUser,
        device_id: UUID,
    ) -> NotificationDevice: ...


class SupabaseNotificationDeviceRepository:
    """Authenticated device lifecycle through safe RPCs that never return push tokens."""

    def __init__(self, client: SupabaseUserRestClient) -> None:
        self._client = client

    async def list_devices(self, user: AuthenticatedUser) -> NotificationDeviceOverview:
        self._ensure_identity(user)
        data = await self._client.rpc("list_janani_notification_devices", {})
        if not isinstance(data, list):
            raise SupabasePersistenceError("Notification device RPC returned an invalid list")
        return NotificationDeviceOverview(devices=[self._map_device(row) for row in data])

    async def register_device(
        self,
        user: AuthenticatedUser,
        payload: NotificationDeviceRegistrationRequest,
    ) -> NotificationDevice:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "register_janani_notification_device",
            {
                "p_installation_id": str(payload.installation_id),
                "p_platform": payload.platform.value,
                "p_transport": payload.transport.value,
                "p_push_token": payload.push_token.get_secret_value(),
                "p_synthetic": payload.synthetic,
            },
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Notification device RPC returned invalid metadata")
        return self._map_device(data)

    async def revoke_device(
        self,
        user: AuthenticatedUser,
        device_id: UUID,
    ) -> NotificationDevice:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "revoke_janani_notification_device",
            {"p_device_id": str(device_id)},
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Notification device RPC returned invalid metadata")
        return self._map_device(data)

    def _map_device(self, row: object) -> NotificationDevice:
        if not isinstance(row, dict):
            raise SupabasePersistenceError("Notification device row is invalid")
        return NotificationDevice(
            device_id=UUID(row["id"]),
            installation_id=UUID(row["installation_id"]),
            platform=NotificationPlatform(row["platform"]),
            transport=NotificationTransportKind(row["transport"]),
            active=bool(row["active"]),
            synthetic=bool(row.get("synthetic", True)),
            registered_at=row.get("registered_at"),
            updated_at=row.get("updated_at"),
            revoked_at=row.get("revoked_at"),
        )

    def _ensure_identity(self, user: AuthenticatedUser) -> None:
        if user.user_id != self._client.user.user_id:
            raise ValueError("Repository identity does not match the authenticated user")
