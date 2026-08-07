from typing import Protocol

from app.notifications.models import (
    NotificationDestination,
    NotificationEnvelope,
    NotificationTransportDisposition,
    NotificationTransportKind,
    NotificationTransportResult,
)


class NotificationTransport(Protocol):
    async def send(
        self,
        destination: NotificationDestination,
        envelope: NotificationEnvelope,
    ) -> NotificationTransportResult: ...


class MockNotificationTransport:
    """Deterministic synthetic transport. It never performs a network request."""

    async def send(
        self,
        destination: NotificationDestination,
        envelope: NotificationEnvelope,
    ) -> NotificationTransportResult:
        if destination.transport is not NotificationTransportKind.MOCK:
            return NotificationTransportResult(
                device_id=destination.device_id,
                disposition=NotificationTransportDisposition.TERMINAL_FAILURE,
                failure_code="unsupported_transport",
            )

        # Access the secret only at the provider boundary. It is never returned or logged.
        token = destination.push_token.get_secret_value()
        if token.startswith("mock-retry:"):
            return NotificationTransportResult(
                device_id=destination.device_id,
                disposition=NotificationTransportDisposition.RETRYABLE_FAILURE,
                failure_code="mock_retryable_failure",
            )
        if token.startswith("mock-terminal:"):
            return NotificationTransportResult(
                device_id=destination.device_id,
                disposition=NotificationTransportDisposition.TERMINAL_FAILURE,
                failure_code="mock_terminal_failure",
            )
        return NotificationTransportResult(
            device_id=destination.device_id,
            disposition=NotificationTransportDisposition.SENT,
        )


def build_generic_reminder_envelope(delivery_id) -> NotificationEnvelope:
    return NotificationEnvelope(delivery_id=delivery_id)
