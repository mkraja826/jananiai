import asyncio
import json
from uuid import UUID

import httpx
from pydantic import SecretStr

from app.notifications.expo import EXPO_PUSH_SEND_URL, ExpoPushTransport
from app.notifications.models import (
    NotificationDestination,
    NotificationEnvelope,
    NotificationPlatform,
    NotificationTransportDisposition,
    NotificationTransportKind,
)

DEVICE_ID = UUID("00000000-0000-0000-0000-000000001301")
DELIVERY_ID = UUID("00000000-0000-0000-0000-000000001302")
ACCESS_TOKEN = SecretStr("synthetic-expo-access-token")
EXPO_TOKEN = "ExpoPushToken[synthetic-phase13-token]"


def destination(
    *,
    platform: NotificationPlatform = NotificationPlatform.ANDROID,
    transport: NotificationTransportKind = NotificationTransportKind.EXPO,
    token: str = EXPO_TOKEN,
) -> NotificationDestination:
    return NotificationDestination(
        device_id=DEVICE_ID,
        platform=platform,
        transport=transport,
        push_token=token,
        synthetic=True,
    )


def run_send(
    handler,
    *,
    target: NotificationDestination | None = None,
):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = ExpoPushTransport(access_token=ACCESS_TOKEN, client=client)

    async def execute():
        try:
            return await transport.send(
                target or destination(),
                NotificationEnvelope(delivery_id=DELIVERY_ID),
            )
        finally:
            await client.aclose()

    return asyncio.run(execute())


def test_expo_transport_sends_only_generic_payload_and_opaque_routing_data() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"data": {"status": "ok", "id": "receipt-1"}})

    result = run_send(handler)

    assert result.disposition is NotificationTransportDisposition.SENT
    assert result.failure_code is None
    assert captured["url"] == EXPO_PUSH_SEND_URL
    assert captured["authorization"] == "Bearer synthetic-expo-access-token"
    assert captured["payload"] == {
        "to": EXPO_TOKEN,
        "title": "Janani reminder",
        "body": "You have a reminder in Janani.",
        "data": {"delivery_id": str(DELIVERY_ID)},
    }


def test_expo_transport_accepts_single_ticket_array_response() -> None:
    result = run_send(
        lambda request: httpx.Response(200, json={"data": [{"status": "ok", "id": "r"}]})
    )

    assert result.disposition is NotificationTransportDisposition.SENT


def test_expo_transport_retries_http_429_and_5xx() -> None:
    for status_code in (429, 500, 503):
        result = run_send(lambda request, code=status_code: httpx.Response(code))

        assert result.disposition is NotificationTransportDisposition.RETRYABLE_FAILURE
        assert result.failure_code == "expo_service_unavailable"


def test_expo_transport_terminally_rejects_http_client_errors_without_raw_body() -> None:
    result = run_send(
        lambda request: httpx.Response(400, text="sensitive synthetic provider explanation")
    )

    assert result.disposition is NotificationTransportDisposition.TERMINAL_FAILURE
    assert result.failure_code == "expo_request_rejected"
    assert "sensitive" not in result.model_dump_json()


def test_expo_transport_retries_network_timeout_without_exception_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic token leaked here", request=request)

    result = run_send(handler)

    assert result.disposition is NotificationTransportDisposition.RETRYABLE_FAILURE
    assert result.failure_code == "expo_service_unavailable"
    assert "leaked" not in result.model_dump_json()


def test_expo_transport_maps_retryable_ticket_errors() -> None:
    for provider_error in ("MessageRateExceeded", "TOO_MANY_REQUESTS"):
        result = run_send(
            lambda request, error=provider_error: httpx.Response(
                200,
                json={
                    "data": {
                        "status": "error",
                        "message": "synthetic provider detail",
                        "details": {"error": error},
                    }
                },
            )
        )

        assert result.disposition is NotificationTransportDisposition.RETRYABLE_FAILURE
        assert result.failure_code == "expo_rate_limited"


def test_expo_transport_maps_known_terminal_ticket_errors_to_opaque_codes() -> None:
    cases = {
        "DeviceNotRegistered": "expo_device_not_registered",
        "MessageTooBig": "expo_message_too_big",
        "MismatchSenderId": "expo_sender_mismatch",
        "InvalidCredentials": "expo_invalid_credentials",
        "UNAUTHORIZED": "expo_unauthorized",
    }
    for provider_error, expected_code in cases.items():
        result = run_send(
            lambda request, error=provider_error: httpx.Response(
                200,
                json={"data": {"status": "error", "details": {"error": error}}},
            )
        )

        assert result.disposition is NotificationTransportDisposition.TERMINAL_FAILURE
        assert result.failure_code == expected_code


def test_expo_transport_retries_unknown_or_malformed_ticket_responses() -> None:
    unknown = run_send(
        lambda request: httpx.Response(
            200,
            json={"data": {"status": "error", "details": {"error": "FutureExpoError"}}},
        )
    )
    malformed = run_send(lambda request: httpx.Response(200, json={"unexpected": True}))
    invalid_json = run_send(lambda request: httpx.Response(200, text="not-json"))

    assert unknown.disposition is NotificationTransportDisposition.RETRYABLE_FAILURE
    assert unknown.failure_code == "expo_unknown_error"
    assert malformed.failure_code == "expo_protocol_error"
    assert invalid_json.failure_code == "expo_protocol_error"


def test_expo_transport_rejects_web_and_invalid_tokens_without_network_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": {"status": "ok"}})

    web = run_send(handler, target=destination(platform=NotificationPlatform.WEB))
    invalid = run_send(handler, target=destination(token="not-an-expo-token"))

    assert web.disposition is NotificationTransportDisposition.TERMINAL_FAILURE
    assert web.failure_code == "unsupported_platform"
    assert invalid.disposition is NotificationTransportDisposition.TERMINAL_FAILURE
    assert invalid.failure_code == "invalid_expo_push_token"
    assert calls == 0


def test_expo_transport_rejects_non_expo_destination_without_network_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": {"status": "ok"}})

    result = run_send(
        handler,
        target=destination(
            transport=NotificationTransportKind.MOCK,
            token="mock-success:synthetic",
        ),
    )

    assert result.disposition is NotificationTransportDisposition.TERMINAL_FAILURE
    assert result.failure_code == "unsupported_transport"
    assert calls == 0
