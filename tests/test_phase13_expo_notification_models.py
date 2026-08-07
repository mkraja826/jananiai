from uuid import UUID

import pytest
from pydantic import ValidationError

from app.notifications.models import (
    NotificationDeviceRegistrationRequest,
    NotificationPlatform,
    NotificationTransportKind,
)

INSTALLATION_ID = UUID("00000000-0000-0000-0000-000000001303")


@pytest.mark.parametrize(
    "token",
    [
        "ExpoPushToken[synthetic-token]",
        "ExponentPushToken[legacy-synthetic-token]",
    ],
)
def test_expo_registration_accepts_current_and_legacy_expo_token_shapes(token: str) -> None:
    payload = NotificationDeviceRegistrationRequest(
        installation_id=INSTALLATION_ID,
        platform=NotificationPlatform.ANDROID,
        transport=NotificationTransportKind.EXPO,
        push_token=token,
    )

    assert payload.transport is NotificationTransportKind.EXPO
    assert payload.push_token.get_secret_value() == token
    assert token not in repr(payload)


def test_expo_registration_rejects_web_platform() -> None:
    with pytest.raises(ValidationError, match="Android and iOS only"):
        NotificationDeviceRegistrationRequest(
            installation_id=INSTALLATION_ID,
            platform=NotificationPlatform.WEB,
            transport=NotificationTransportKind.EXPO,
            push_token="ExpoPushToken[synthetic-token]",
        )


def test_expo_registration_rejects_non_expo_token() -> None:
    with pytest.raises(ValidationError, match="valid Expo push token"):
        NotificationDeviceRegistrationRequest(
            installation_id=INSTALLATION_ID,
            platform=NotificationPlatform.IOS,
            transport=NotificationTransportKind.EXPO,
            push_token="not-an-expo-token",
        )


def test_mock_registration_behavior_remains_unchanged() -> None:
    payload = NotificationDeviceRegistrationRequest(
        installation_id=INSTALLATION_ID,
        platform=NotificationPlatform.WEB,
        transport=NotificationTransportKind.MOCK,
        push_token="mock-success:synthetic",
    )

    assert payload.transport is NotificationTransportKind.MOCK
