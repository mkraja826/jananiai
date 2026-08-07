from uuid import UUID

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.notifications.dependencies import get_notification_device_repository
from app.notifications.models import (
    NotificationDevice,
    NotificationDeviceOverview,
    NotificationDeviceRegistrationRequest,
    NotificationPlatform,
    NotificationTransportKind,
)

DEVICE_ID = UUID("00000000-0000-0000-0000-000000001111")
INSTALLATION_ID = UUID("00000000-0000-0000-0000-000000001112")


class FakeNotificationDeviceRepository:
    async def list_devices(self, user) -> NotificationDeviceOverview:
        return NotificationDeviceOverview(devices=[self._device(active=True)])

    async def register_device(
        self,
        user,
        payload: NotificationDeviceRegistrationRequest,
    ) -> NotificationDevice:
        return NotificationDevice(
            device_id=DEVICE_ID,
            installation_id=payload.installation_id,
            platform=payload.platform,
            transport=payload.transport,
            active=True,
            synthetic=payload.synthetic,
        )

    async def revoke_device(self, user, device_id: UUID) -> NotificationDevice:
        assert device_id == DEVICE_ID
        return self._device(active=False)

    def _device(self, *, active: bool) -> NotificationDevice:
        return NotificationDevice(
            device_id=DEVICE_ID,
            installation_id=INSTALLATION_ID,
            platform=NotificationPlatform.ANDROID,
            transport=NotificationTransportKind.MOCK,
            active=active,
        )


def client() -> TestClient:
    application = create_app(settings=Settings(environment="test", free_first_mode=True))
    application.dependency_overrides[get_notification_device_repository] = lambda: (
        FakeNotificationDeviceRepository()
    )
    return TestClient(application)


def test_register_device_api_never_echoes_push_token() -> None:
    raw_token = "mock-success:synthetic-api-token"
    response = client().post(
        "/v1/notifications/devices",
        json={
            "installation_id": str(INSTALLATION_ID),
            "platform": "android",
            "transport": "mock",
            "push_token": raw_token,
            "synthetic": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["device_id"] == str(DEVICE_ID)
    assert payload["installation_id"] == str(INSTALLATION_ID)
    assert payload["active"] is True
    assert "push_token" not in payload
    assert raw_token not in response.text


def test_list_devices_api_returns_safe_metadata_only() -> None:
    response = client().get("/v1/notifications/devices")

    assert response.status_code == 200
    payload = response.json()["devices"][0]
    assert payload["device_id"] == str(DEVICE_ID)
    assert "push_token" not in payload
    assert "token_fingerprint" not in payload


def test_revoke_device_api_returns_inactive_metadata() -> None:
    response = client().post(f"/v1/notifications/devices/{DEVICE_ID}/revoke")

    assert response.status_code == 200
    assert response.json()["active"] is False
    assert "push_token" not in response.json()


def test_real_device_mode_is_blocked_in_free_first_environment() -> None:
    response = client().post(
        "/v1/notifications/devices",
        json={
            "installation_id": str(INSTALLATION_ID),
            "platform": "android",
            "transport": "mock",
            "push_token": "mock-success:synthetic-api-token",
            "synthetic": False,
        },
    )

    assert response.status_code == 403
    assert "Real patient data" in response.json()["detail"]
