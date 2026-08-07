import os
from uuid import UUID, uuid4

import httpx
import pytest

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


def test_reminder_materialization_claim_retry_response_and_cancellation() -> None:
    assert USER_A_ID and USER_A_TOKEN and USER_B_TOKEN

    medication_id = str(uuid4())
    medication = httpx.post(
        rest_url("medication_records"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "id": medication_id,
            "user_id": USER_A_ID,
            "name": "Synthetic explicit reminder medication",
            "source": "user_entered",
            "confirmed": True,
            "active": True,
        },
        timeout=20,
    )
    medication.raise_for_status()

    reminder_response = httpx.post(
        rest_url("rpc/create_janani_medication_reminder"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_medication_id": medication_id,
            "p_local_time": "08:30:00",
            "p_timezone_name": "Asia/Kolkata",
            "p_start_date": "2030-01-01",
            "p_end_date": None,
            "p_weekdays": [1, 2, 3, 4, 5, 6, 7],
            "p_synthetic": True,
        },
        timeout=20,
    )
    reminder_response.raise_for_status()
    reminder_id = reminder_response.json()["id"]

    materialized = httpx.post(
        rest_url("rpc/materialize_janani_reminder_deliveries"),
        headers=service_headers(),
        json={
            "p_window_start": "2030-01-01T02:59:00Z",
            "p_window_end": "2030-01-01T03:01:00Z",
        },
        timeout=20,
    )
    materialized.raise_for_status()
    assert materialized.json() >= 1

    owner_jobs = httpx.get(
        rest_url("reminder_delivery_jobs"),
        headers=headers(USER_A_TOKEN),
        params={
            "select": "id,status,scheduled_for,origin,medication_reminder_id,attempt_count",
            "medication_reminder_id": f"eq.{reminder_id}",
            "scheduled_for": "eq.2030-01-01T03:00:00+00:00",
        },
        timeout=20,
    )
    owner_jobs.raise_for_status()
    assert len(owner_jobs.json()) == 1
    job = owner_jobs.json()[0]
    delivery_id = job["id"]
    assert job["status"] == "pending"
    assert job["origin"] == "schedule"

    cross_read = httpx.get(
        rest_url("reminder_delivery_jobs"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id", "id": f"eq.{delivery_id}"},
        timeout=20,
    )
    cross_read.raise_for_status()
    assert cross_read.json() == []

    direct_forge = httpx.post(
        rest_url("reminder_delivery_jobs"),
        headers=headers(USER_A_TOKEN),
        json={
            "user_id": USER_A_ID,
            "reminder_kind": "medication",
            "medication_reminder_id": reminder_id,
            "scheduled_for": "2030-01-01T04:30:00Z",
            "next_attempt_at": "2030-01-01T04:30:00Z",
        },
        timeout=20,
    )
    assert_denied(direct_forge)

    claimed = httpx.post(
        rest_url("rpc/claim_janani_reminder_deliveries"),
        headers=service_headers(),
        json={"p_now": "2030-01-01T03:00:30Z", "p_limit": 100},
        timeout=20,
    )
    claimed.raise_for_status()
    our_claim = next(item for item in claimed.json() if item["id"] == delivery_id)
    UUID(our_claim["claim_token"])
    assert our_claim["attempt_count"] == 1

    sent = httpx.post(
        rest_url("rpc/complete_janani_reminder_delivery"),
        headers=service_headers(),
        json={
            "p_delivery_id": delivery_id,
            "p_claim_token": our_claim["claim_token"],
            "p_outcome": "sent",
            "p_now": "2030-01-01T03:00:31Z",
            "p_failure_code": None,
        },
        timeout=20,
    )
    sent.raise_for_status()
    assert sent.json()["status"] == "sent"
    assert sent.json()["completed_at"].startswith("2030-01-01T03:00:31")

    cross_response = httpx.post(
        rest_url("rpc/record_janani_reminder_response"),
        headers=headers(USER_B_TOKEN),
        json={
            "p_client_event_id": str(uuid4()),
            "p_delivery_id": delivery_id,
            "p_event_type": "acknowledged",
            "p_occurred_at": "2030-01-01T03:05:00Z",
            "p_remind_at": None,
            "p_synthetic": True,
        },
        timeout=20,
    )
    assert_denied(cross_response)

    client_event_id = str(uuid4())
    response_payload = {
        "p_client_event_id": client_event_id,
        "p_delivery_id": delivery_id,
        "p_event_type": "remind_later",
        "p_occurred_at": "2030-01-01T03:05:00Z",
        "p_remind_at": "2030-01-01T04:00:00Z",
        "p_synthetic": True,
    }
    response_event = httpx.post(
        rest_url("rpc/record_janani_reminder_response"),
        headers=headers(USER_A_TOKEN),
        json=response_payload,
        timeout=20,
    )
    response_event.raise_for_status()
    response_id = response_event.json()["id"]
    UUID(response_id)

    idempotent_repeat = httpx.post(
        rest_url("rpc/record_janani_reminder_response"),
        headers=headers(USER_A_TOKEN),
        json=response_payload,
        timeout=20,
    )
    idempotent_repeat.raise_for_status()
    assert idempotent_repeat.json()["id"] == response_id

    remind_later_jobs = httpx.get(
        rest_url("reminder_delivery_jobs"),
        headers=headers(USER_A_TOKEN),
        params={
            "select": "id,status,origin,attempt_count",
            "medication_reminder_id": f"eq.{reminder_id}",
            "scheduled_for": "eq.2030-01-01T04:00:00+00:00",
        },
        timeout=20,
    )
    remind_later_jobs.raise_for_status()
    assert len(remind_later_jobs.json()) == 1
    retry_job = remind_later_jobs.json()[0]
    assert retry_job["origin"] == "remind_later"

    retry_claim = httpx.post(
        rest_url("rpc/claim_janani_reminder_deliveries"),
        headers=service_headers(),
        json={"p_now": "2030-01-01T04:00:30Z", "p_limit": 100},
        timeout=20,
    )
    retry_claim.raise_for_status()
    claimed_retry = next(item for item in retry_claim.json() if item["id"] == retry_job["id"])

    retryable_failure = httpx.post(
        rest_url("rpc/complete_janani_reminder_delivery"),
        headers=service_headers(),
        json={
            "p_delivery_id": retry_job["id"],
            "p_claim_token": claimed_retry["claim_token"],
            "p_outcome": "retryable_failure",
            "p_now": "2030-01-01T04:00:31Z",
            "p_failure_code": "synthetic_transport_timeout",
        },
        timeout=20,
    )
    retryable_failure.raise_for_status()
    assert retryable_failure.json()["status"] == "pending"
    assert retryable_failure.json()["attempt_count"] == 1
    assert retryable_failure.json()["next_attempt_at"].startswith("2030-01-01T04:05:31")

    second_claim = httpx.post(
        rest_url("rpc/claim_janani_reminder_deliveries"),
        headers=service_headers(),
        json={"p_now": "2030-01-01T04:05:32Z", "p_limit": 100},
        timeout=20,
    )
    second_claim.raise_for_status()
    claimed_second = next(item for item in second_claim.json() if item["id"] == retry_job["id"])
    assert claimed_second["attempt_count"] == 2

    terminal = httpx.post(
        rest_url("rpc/complete_janani_reminder_delivery"),
        headers=service_headers(),
        json={
            "p_delivery_id": retry_job["id"],
            "p_claim_token": claimed_second["claim_token"],
            "p_outcome": "terminal_failure",
            "p_now": "2030-01-01T04:05:33Z",
            "p_failure_code": "synthetic_terminal_failure",
        },
        timeout=20,
    )
    terminal.raise_for_status()
    assert terminal.json()["status"] == "failed"

    next_day = httpx.post(
        rest_url("rpc/materialize_janani_reminder_deliveries"),
        headers=service_headers(),
        json={
            "p_window_start": "2030-01-02T02:59:00Z",
            "p_window_end": "2030-01-02T03:01:00Z",
        },
        timeout=20,
    )
    next_day.raise_for_status()

    next_day_jobs = httpx.get(
        rest_url("reminder_delivery_jobs"),
        headers=headers(USER_A_TOKEN),
        params={
            "select": "id,status",
            "medication_reminder_id": f"eq.{reminder_id}",
            "scheduled_for": "eq.2030-01-02T03:00:00+00:00",
        },
        timeout=20,
    )
    next_day_jobs.raise_for_status()
    assert len(next_day_jobs.json()) == 1
    next_delivery_id = next_day_jobs.json()[0]["id"]
    assert next_day_jobs.json()[0]["status"] == "pending"

    disabled = httpx.post(
        rest_url("rpc/disable_janani_reminder"),
        headers=headers(USER_A_TOKEN),
        json={"p_reminder_kind": "medication", "p_reminder_id": reminder_id},
        timeout=20,
    )
    disabled.raise_for_status()

    cancelled = httpx.get(
        rest_url("reminder_delivery_jobs"),
        headers=headers(USER_A_TOKEN),
        params={"select": "status", "id": f"eq.{next_delivery_id}"},
        timeout=20,
    )
    cancelled.raise_for_status()
    assert cancelled.json() == [{"status": "cancelled"}]
