import os
from uuid import uuid4

import httpx
import pytest

SUPABASE_URL = os.getenv("JANANI_STAGING_SUPABASE_URL")
PUBLISHABLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_PUBLISHABLE_KEY")
SERVICE_ROLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_SERVICE_ROLE_KEY")
USER_A_TOKEN = os.getenv("JANANI_STAGING_USER_A_TOKEN")
USER_B_TOKEN = os.getenv("JANANI_STAGING_USER_B_TOKEN")

_REQUIRED = [
    SUPABASE_URL,
    PUBLISHABLE_KEY,
    SERVICE_ROLE_KEY,
    USER_A_TOKEN,
    USER_B_TOKEN,
]

pytestmark = [
    pytest.mark.staging,
    pytest.mark.skipif(
        not all(_REQUIRED),
        reason="Dedicated synthetic Supabase staging credentials are not configured",
    ),
]


def headers(
    token: str,
    *,
    api_key: str | None = None,
) -> dict[str, str]:
    return {
        "apikey": api_key or PUBLISHABLE_KEY or "",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def service_headers() -> dict[str, str]:
    key = SERVICE_ROLE_KEY or ""
    return headers(key, api_key=key)


def rest_url(path: str) -> str:
    assert SUPABASE_URL is not None
    return f"{SUPABASE_URL}/rest/v1/{path}"


def register(
    user_token: str,
    *,
    installation_id,
    platform: str,
    push_token: str,
) -> httpx.Response:
    return httpx.post(
        rest_url("rpc/register_janani_notification_device"),
        headers=headers(user_token),
        json={
            "p_installation_id": str(installation_id),
            "p_platform": platform,
            "p_transport": "expo",
            "p_push_token": push_token,
            "p_synthetic": True,
        },
        timeout=20,
    )


def test_expo_registration_is_guarded_and_raw_token_remains_backend_only() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN
    installation_id = uuid4()
    raw_token = f"ExpoPushToken[phase13-{uuid4()}]"

    created = register(
        USER_A_TOKEN,
        installation_id=installation_id,
        platform="android",
        push_token=raw_token,
    )
    created.raise_for_status()
    device_id = created.json()["id"]
    assert created.json()["transport"] == "expo"
    assert created.json()["platform"] == "android"
    assert "push_token" not in created.json()
    assert "token_fingerprint" not in created.json()
    assert raw_token not in created.text

    raw_read = httpx.get(
        rest_url("notification_devices"),
        headers=headers(USER_A_TOKEN),
        params={"select": "*", "id": f"eq.{device_id}"},
        timeout=20,
    )
    assert raw_read.status_code in {400, 401, 403, 404}, raw_read.text

    service_read = httpx.get(
        rest_url("notification_devices"),
        headers=service_headers(),
        params={"select": "id,transport,push_token", "id": f"eq.{device_id}"},
        timeout=20,
    )
    service_read.raise_for_status()
    assert service_read.json() == [{"id": device_id, "transport": "expo", "push_token": raw_token}]

    cross_user = register(
        USER_B_TOKEN,
        installation_id=uuid4(),
        platform="ios",
        push_token=raw_token,
    )
    assert cross_user.status_code == 409, cross_user.text

    web = register(
        USER_A_TOKEN,
        installation_id=uuid4(),
        platform="web",
        push_token=f"ExpoPushToken[phase13-web-{uuid4()}]",
    )
    assert web.status_code == 400, web.text

    malformed = register(
        USER_A_TOKEN,
        installation_id=uuid4(),
        platform="ios",
        push_token="not-an-expo-token",
    )
    assert malformed.status_code == 400, malformed.text

    revoked = httpx.post(
        rest_url("rpc/revoke_janani_notification_device"),
        headers=headers(USER_A_TOKEN),
        json={"p_device_id": device_id},
        timeout=20,
    )
    revoked.raise_for_status()
    assert revoked.json()["active"] is False
    assert "push_token" not in revoked.json()
