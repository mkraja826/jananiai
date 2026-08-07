import asyncio
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.notifications.models import (
    NotificationDestination,
    NotificationDevice,
    NotificationDeviceRegistrationRequest,
    NotificationEnvelope,
    NotificationPlatform,
    NotificationTransportDisposition,
    NotificationTransportKind,
)
from app.notifications.transport import MockNotificationTransport, build_generic_reminder_envelope

DELIVERY_ID = UUID("00000000-0000-0000-0000-000000001101")
DEVICE_ID = UUID("00000000-0000-0000-0000-000000001102")
INSTALLATION_ID = UUID("00000000-0000-0000-0000-000000001103")


def test_push_token_is_secret_and_not_part_of_safe_device_metadata() -> None:
    raw_token = "mock-success:synthetic-secret-token"
    request = NotificationDeviceRegistrationRequest(
        installation_id=INSTALLATION_ID,
        platform=NotificationPlatform.ANDROID,
        transport=NotificationTransportKind.MOCK,
        push_token=raw_token,
    )
    device = NotificationDevice(
        device_id=DEVICE_ID,
        installation_id=INSTALLATION_ID,
        platform=NotificationPlatform.ANDROID,
        transport=NotificationTransportKind.MOCK,
        active=True,
    )

    assert raw_token not in repr(request)
    assert raw_token not in request.model_dump_json()
    assert "push_token" not in device.model_dump()


def test_push_token_length_is_bounded() -> None:
    with pytest.raises(ValidationError):
        NotificationDeviceRegistrationRequest(
            installation_id=INSTALLATION_ID,
            platform=NotificationPlatform.ANDROID,
            push_token="short",
        )


def test_generic_envelope_contains_only_neutral_content_and_opaque_delivery_id() -> None:
    envelope = build_generic_reminder_envelope(DELIVERY_ID)

    assert envelope == NotificationEnvelope(delivery_id=DELIVERY_ID)
    assert envelope.title == "Janani reminder"
    assert envelope.body == "You have a reminder in Janani."
    assert envelope.transport_data() == {"delivery_id": str(DELIVERY_ID)}
    serialized = envelope.model_dump_json().lower()
    for prohibited in (
        "medication",
        "dose",
        "appointment",
        "symptom",
        "report",
        "diagnosis",
        "treatment",
    ):
        assert prohibited not in serialized


def test_mock_transport_is_deterministic_and_returns_no_token() -> None:
    async def run() -> None:
        transport = MockNotificationTransport()
        envelope = build_generic_reminder_envelope(DELIVERY_ID)
        sent = await transport.send(
            NotificationDestination(
                device_id=DEVICE_ID,
                platform=NotificationPlatform.ANDROID,
                transport=NotificationTransportKind.MOCK,
                push_token="mock-success:synthetic-token",
            ),
            envelope,
        )
        retryable = await transport.send(
            NotificationDestination(
                device_id=DEVICE_ID,
                platform=NotificationPlatform.ANDROID,
                transport=NotificationTransportKind.MOCK,
                push_token="mock-retry:synthetic-token",
            ),
            envelope,
        )
        terminal = await transport.send(
            NotificationDestination(
                device_id=DEVICE_ID,
                platform=NotificationPlatform.ANDROID,
                transport=NotificationTransportKind.MOCK,
                push_token="mock-terminal:synthetic-token",
            ),
            envelope,
        )

        assert sent.disposition is NotificationTransportDisposition.SENT
        assert retryable.disposition is NotificationTransportDisposition.RETRYABLE_FAILURE
        assert terminal.disposition is NotificationTransportDisposition.TERMINAL_FAILURE
        for result in (sent, retryable, terminal):
            assert "token" not in result.model_dump_json().lower()

    asyncio.run(run())
