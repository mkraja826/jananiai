import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest

from app.notifications.dispatch import ReminderNotificationDispatcher
from app.notifications.transport import MockNotificationTransport
from app.notifications.worker import SupabaseNotificationWorkerRepository
from app.reminders.worker import SupabaseReminderDeliveryWorkerRepository

SUPABASE_URL = os.getenv("JANANI_STAGING_SUPABASE_URL")
PUBLISHABLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_PUBLISHABLE_KEY")
SERVICE_ROLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_SERVICE_ROLE_KEY")
USER_A_ID = os.getenv("JANANI_STAGING_USER_A_ID")
USER_A_TOKEN = os.getenv("JANANI_STAGING_USER_A_TOKEN")
USER_B_TOKEN = os.getenv("JANANI_STAGING_USER_B_TOKEN")

_REQUIRED = [
    SUPABASE_URL,
    PUBLISHABLE_KEY,
    SERVICE_ROLE_KEY,
    USER_A_ID,
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
    prefer: str | None = None,
) -> dict[str, str]:
    result = {
        "apikey": api_key or PUBLISHABLE_KEY or "",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if prefer:
        result["Prefer"] = prefer
    return result


def service_headers() -> dict[str, str]:
    key = SERVICE_ROLE_KEY or ""
    return headers(key, api_key=key)


def rest_url(path: str) -> str:
    assert SUPABASE_URL is not None
    return f"{SUPABASE_URL}/rest/v1/{path}"


def assert_denied(response: httpx.Response) -> None:
    assert response.status_code in {400, 401, 403, 404, 409}, response.text


def register_device(token: str, installation_id: UUID, push_token: str) -> httpx.Response:
    return httpx.post(
        rest_url("rpc/register_janani_notification_device"),
        headers=headers(token),
        json={
            "p_installation_id": str(installation_id),
            "p_platform": "android",
            "p_transport": "mock",
            "p_push_token": push_token,
            "p_synthetic": True,
        },
        timeout=20,
    )


def create_claimed_medication_delivery(*, local_date: str) -> tuple[str, str]:
    assert USER_A_ID and USER_A_TOKEN
    medication_id = str(uuid4())
    medication = httpx.post(
        rest_url("medication_records"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "id": medication_id,
            "user_id": USER_A_ID,
            "name": "Synthetic notification reminder target",
            "source": "user_entered",
            "confirmed": True,
            "active": True,
        },
        timeout=20,
    )
    medication.raise_for_status()

    reminder = httpx.post(
        rest_url("rpc/create_janani_medication_reminder"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_medication_id": medication_id,
            "p_local_time": "08:30:00",
            "p_timezone_name": "Asia/Kolkata",
            "p_start_date": local_date,
            "p_end_date": local_date,
            "p_weekdays": [1, 2, 3, 4, 5, 6, 7],
            "p_synthetic": True,
        },
        timeout=20,
    )
    reminder.raise_for_status()
    reminder_id = reminder.json()["id"]

    occurrence = datetime.fromisoformat(f"{local_date}T08:30:00+05:30").astimezone(UTC)
    window_start = occurrence.replace(second=0) - __import__("datetime").timedelta(minutes=1)
    window_end = occurrence.replace(second=0) + __import__("datetime").timedelta(minutes=1)

    materialized = httpx.post(
        rest_url("rpc/materialize_janani_reminder_deliveries"),
        headers=service_headers(),
        json={
            "p_window_start": window_start.isoformat(),
            "p_window_end": window_end.isoformat(),
        },
        timeout=20,
    )
    materialized.raise_for_status()

    jobs = httpx.get(
        rest_url("reminder_delivery_jobs"),
        headers=headers(USER_A_TOKEN),
        params={
            "select": "id",
            "medication_reminder_id": f"eq.{reminder_id}",
            "scheduled_for": f"eq.{occurrence.isoformat()}",
        },
        timeout=20,
    )
    jobs.raise_for_status()
    assert len(jobs.json()) == 1
    return jobs.json()[0]["id"], occurrence.isoformat()


def test_notification_device_lifecycle_is_private_and_claim_bound() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN
    installation_id = uuid4()
    token_v1 = f"mock-success:phase11-v1-{uuid4()}"
    token_v2 = f"mock-success:phase11-v2-{uuid4()}"

    first = register_device(USER_A_TOKEN, installation_id, token_v1)
    first.raise_for_status()
    device_id = first.json()["id"]
    assert first.json()["active"] is True
    assert "push_token" not in first.json()
    assert "token_fingerprint" not in first.json()
    assert token_v1 not in first.text

    direct_read = httpx.get(
        rest_url("notification_devices"),
        headers=headers(USER_A_TOKEN),
        params={"select": "*"},
        timeout=20,
    )
    assert_denied(direct_read)

    direct_write = httpx.post(
        rest_url("notification_devices"),
        headers=headers(USER_A_TOKEN),
        json={
            "installation_id": str(uuid4()),
            "platform": "android",
            "transport": "mock",
            "push_token": "mock-success:forged-token",
            "token_fingerprint": "0" * 64,
        },
        timeout=20,
    )
    assert_denied(direct_write)

    user_a_list = httpx.post(
        rest_url("rpc/list_janani_notification_devices"),
        headers=headers(USER_A_TOKEN),
        json={},
        timeout=20,
    )
    user_a_list.raise_for_status()
    listed = next(item for item in user_a_list.json() if item["id"] == device_id)
    assert "push_token" not in listed
    assert "token_fingerprint" not in listed

    user_b_list = httpx.post(
        rest_url("rpc/list_janani_notification_devices"),
        headers=headers(USER_B_TOKEN),
        json={},
        timeout=20,
    )
    user_b_list.raise_for_status()
    assert device_id not in {item["id"] for item in user_b_list.json()}

    cross_revoke = httpx.post(
        rest_url("rpc/revoke_janani_notification_device"),
        headers=headers(USER_B_TOKEN),
        json={"p_device_id": device_id},
        timeout=20,
    )
    assert_denied(cross_revoke)

    rotated = register_device(USER_A_TOKEN, installation_id, token_v2)
    rotated.raise_for_status()
    assert rotated.json()["id"] == device_id
    assert token_v2 not in rotated.text

    duplicate_other_user = register_device(USER_B_TOKEN, uuid4(), token_v2)
    assert duplicate_other_user.status_code == 409, duplicate_other_user.text

    delivery_id, occurrence = create_claimed_medication_delivery(local_date="2032-02-03")
    claim = httpx.post(
        rest_url("rpc/claim_janani_reminder_deliveries"),
        headers=service_headers(),
        json={"p_now": occurrence, "p_limit": 100},
        timeout=20,
    )
    claim.raise_for_status()
    claimed = next(item for item in claim.json() if item["id"] == delivery_id)
    claim_token = claimed["claim_token"]

    user_destination_attempt = httpx.post(
        rest_url("rpc/get_janani_notification_destinations"),
        headers=headers(USER_A_TOKEN),
        json={"p_delivery_id": delivery_id, "p_claim_token": claim_token},
        timeout=20,
    )
    assert_denied(user_destination_attempt)

    destinations = httpx.post(
        rest_url("rpc/get_janani_notification_destinations"),
        headers=service_headers(),
        json={"p_delivery_id": delivery_id, "p_claim_token": claim_token},
        timeout=20,
    )
    destinations.raise_for_status()
    our_destination = next(item for item in destinations.json() if item["id"] == device_id)
    assert our_destination["push_token"] == token_v2
    assert our_destination["synthetic"] is True

    stale_claim = httpx.post(
        rest_url("rpc/get_janani_notification_destinations"),
        headers=service_headers(),
        json={"p_delivery_id": delivery_id, "p_claim_token": str(uuid4())},
        timeout=20,
    )
    assert stale_claim.status_code == 400, stale_claim.text

    revoked = httpx.post(
        rest_url("rpc/revoke_janani_notification_device"),
        headers=headers(USER_A_TOKEN),
        json={"p_device_id": device_id},
        timeout=20,
    )
    revoked.raise_for_status()
    assert revoked.json()["active"] is False
    assert "push_token" not in revoked.json()

    after_revoke = httpx.post(
        rest_url("rpc/get_janani_notification_destinations"),
        headers=service_headers(),
        json={"p_delivery_id": delivery_id, "p_claim_token": claim_token},
        timeout=20,
    )
    after_revoke.raise_for_status()
    assert device_id not in {item["id"] for item in after_revoke.json()}

    completed = httpx.post(
        rest_url("rpc/complete_janani_reminder_delivery"),
        headers=service_headers(),
        json={
            "p_delivery_id": delivery_id,
            "p_claim_token": claim_token,
            "p_outcome": "terminal_failure",
            "p_now": "2032-02-03T03:00:31Z",
            "p_failure_code": "synthetic_test_cleanup",
        },
        timeout=20,
    )
    completed.raise_for_status()


def test_mock_dispatcher_completes_claimed_queue_job_as_sent() -> None:
    assert SUPABASE_URL and SERVICE_ROLE_KEY and USER_A_TOKEN
    installation_id = uuid4()
    raw_token = f"mock-success:phase11-dispatch-{uuid4()}"
    registered = register_device(USER_A_TOKEN, installation_id, raw_token)
    registered.raise_for_status()

    delivery_id, occurrence_text = create_claimed_medication_delivery(local_date="2033-02-03")
    occurrence = datetime.fromisoformat(occurrence_text)
    dispatch_now = occurrence.replace(second=30)

    async def run() -> None:
        queue = SupabaseReminderDeliveryWorkerRepository(
            supabase_url=SUPABASE_URL,
            service_role_key=SERVICE_ROLE_KEY,
        )
        destinations = SupabaseNotificationWorkerRepository(
            supabase_url=SUPABASE_URL,
            service_role_key=SERVICE_ROLE_KEY,
        )
        dispatcher = ReminderNotificationDispatcher(
            queue=queue,
            destinations=destinations,
            transport=MockNotificationTransport(),
        )
        try:
            claims = await queue.claim(now=dispatch_now, limit=100)
            our_claim = next(item for item in claims if str(item.delivery_id) == delivery_id)
            result = await dispatcher.dispatch_claim(claim=our_claim, now=dispatch_now)
            assert result.disposition.value == "sent"
            assert result.sent_count >= 1
            assert result.destination_count >= 1
        finally:
            await queue.aclose()
            await destinations.aclose()

    asyncio.run(run())

    job = httpx.get(
        rest_url("reminder_delivery_jobs"),
        headers=headers(USER_A_TOKEN),
        params={"select": "id,status,attempt_count", "id": f"eq.{delivery_id}"},
        timeout=20,
    )
    job.raise_for_status()
    assert job.json()[0]["status"] == "sent"
