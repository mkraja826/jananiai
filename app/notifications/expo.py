import httpx
from pydantic import SecretStr

from app.notifications.models import (
    NotificationDestination,
    NotificationEnvelope,
    NotificationPlatform,
    NotificationTransportDisposition,
    NotificationTransportKind,
    NotificationTransportResult,
    is_valid_expo_push_token,
)

EXPO_PUSH_SEND_URL = "https://exp.host/--/api/v2/push/send"

_RETRYABLE_TICKET_ERRORS = {
    "MessageRateExceeded",
    "TOO_MANY_REQUESTS",
}

_TERMINAL_TICKET_ERRORS = {
    "DeviceNotRegistered",
    "MessageTooBig",
    "MismatchSenderId",
    "InvalidCredentials",
    "PUSH_TOO_MANY_EXPERIENCE_IDS",
    "PUSH_TOO_MANY_NOTIFICATIONS",
    "UNAUTHORIZED",
}


class ExpoPushTransport:
    """Backend-only Expo Push adapter with generic notification content only."""

    def __init__(
        self,
        *,
        access_token: SecretStr,
        timeout_seconds: float = 8.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        token = access_token.get_secret_value().strip()
        if not token:
            raise ValueError("Expo push access token is required")
        if timeout_seconds <= 0:
            raise ValueError("Expo push timeout must be positive")

        self._access_token = SecretStr(token)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def send(
        self,
        destination: NotificationDestination,
        envelope: NotificationEnvelope,
    ) -> NotificationTransportResult:
        if destination.transport is not NotificationTransportKind.EXPO:
            return self._terminal(destination, "unsupported_transport")
        if destination.platform is NotificationPlatform.WEB:
            return self._terminal(destination, "unsupported_platform")

        push_token = destination.push_token.get_secret_value().strip()
        if not is_valid_expo_push_token(push_token):
            return self._terminal(destination, "invalid_expo_push_token")

        payload = {
            "to": push_token,
            "title": envelope.title,
            "body": envelope.body,
            "data": envelope.transport_data(),
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token.get_secret_value()}",
        }

        try:
            response = await self._client.post(
                EXPO_PUSH_SEND_URL,
                json=payload,
                headers=headers,
            )
        except (httpx.TimeoutException, httpx.NetworkError):
            return self._retryable(destination, "expo_service_unavailable")
        except httpx.HTTPError:
            return self._retryable(destination, "expo_transport_error")

        if response.status_code == 429 or response.status_code >= 500:
            return self._retryable(destination, "expo_service_unavailable")
        if response.status_code >= 400:
            return self._terminal(destination, "expo_request_rejected")

        try:
            body = response.json()
        except ValueError:
            return self._retryable(destination, "expo_protocol_error")

        ticket = self._extract_ticket(body)
        if ticket is None:
            return self._retryable(destination, "expo_protocol_error")

        status = ticket.get("status")
        if status == "ok":
            return NotificationTransportResult(
                device_id=destination.device_id,
                disposition=NotificationTransportDisposition.SENT,
            )
        if status != "error":
            return self._retryable(destination, "expo_protocol_error")

        details = ticket.get("details")
        provider_error = details.get("error") if isinstance(details, dict) else None
        if provider_error in _RETRYABLE_TICKET_ERRORS:
            return self._retryable(destination, "expo_rate_limited")
        if provider_error in _TERMINAL_TICKET_ERRORS:
            return self._terminal(destination, self._terminal_code(provider_error))
        return self._retryable(destination, "expo_unknown_error")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _extract_ticket(body: object) -> dict[str, object] | None:
        if not isinstance(body, dict):
            return None
        data = body.get("data")
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
            return data[0]
        return None

    @staticmethod
    def _terminal_code(provider_error: object) -> str:
        mapping = {
            "DeviceNotRegistered": "expo_device_not_registered",
            "MessageTooBig": "expo_message_too_big",
            "MismatchSenderId": "expo_sender_mismatch",
            "InvalidCredentials": "expo_invalid_credentials",
            "PUSH_TOO_MANY_EXPERIENCE_IDS": "expo_project_mismatch",
            "PUSH_TOO_MANY_NOTIFICATIONS": "expo_batch_too_large",
            "UNAUTHORIZED": "expo_unauthorized",
        }
        return mapping.get(provider_error, "expo_terminal_error")

    @staticmethod
    def _retryable(
        destination: NotificationDestination,
        failure_code: str,
    ) -> NotificationTransportResult:
        return NotificationTransportResult(
            device_id=destination.device_id,
            disposition=NotificationTransportDisposition.RETRYABLE_FAILURE,
            failure_code=failure_code,
        )

    @staticmethod
    def _terminal(
        destination: NotificationDestination,
        failure_code: str,
    ) -> NotificationTransportResult:
        return NotificationTransportResult(
            device_id=destination.device_id,
            disposition=NotificationTransportDisposition.TERMINAL_FAILURE,
            failure_code=failure_code,
        )
