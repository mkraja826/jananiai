from datetime import datetime, timezone
from uuid import UUID

import httpx
import pytest

from app.reminders.models import ReminderDispatchOutcome
from app.reminders.worker import SupabaseReminderDeliveryWorkerRepository

DELIVERY_ID = UUID("00000000-0000-0000-0000-000000001021")
REMINDER_ID = UUID("00000000-0000-0000-0000-000000001022")
CLAIM_TOKEN = UUID("00000000-0000-0000-0000-000000001023")


def transport(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/materialize_janani_reminder_deliveries"):
        return httpx.Response(200, json=2)
    if request.url.path.endswith("/claim_janani_reminder_deliveries"):
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(DELIVERY_ID),
                    "reminder_kind": "medication",
                    "medication_reminder_id": str(REMINDER_ID),
                    "appointment_reminder_id": None,
                    "scheduled_for": "2030-01-01T03:00:00Z",
                    "origin": "schedule",
                    "status": "claimed",
                    "attempt_count": 1,
                    "claim_token": str(CLAIM_TOKEN),
                    "claimed_at": "2030-01-01T03:00:30Z",
                    "synthetic": True,
                    "created_at": "2029-12-31T00:00:00Z",
                    "completed_at": None,
                }
            ],
        )
    if request.url.path.endswith("/complete_janani_reminder_delivery"):
        return httpx.Response(
            200,
            json={
                "id": str(DELIVERY_ID),
                "reminder_kind": "medication",
                "medication_reminder_id": str(REMINDER_ID),
                "appointment_reminder_id": None,
                "scheduled_for": "2030-01-01T03:00:00Z",
                "origin": "schedule",
                "status": "sent",
                "attempt_count": 1,
                "synthetic": True,
                "created_at": "2029-12-31T00:00:00Z",
                "completed_at": "2030-01-01T03:00:31Z",
            },
        )
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_worker_materializes_claims_and_completes_opaque_jobs() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    repository = SupabaseReminderDeliveryWorkerRepository(
        supabase_url="https://synthetic.supabase.co",
        service_role_key="synthetic-service-role",
        client=client,
    )

    count = await repository.materialize(
        window_start=datetime(2030, 1, 1, 2, 0, tzinfo=timezone.utc),
        window_end=datetime(2030, 1, 1, 4, 0, tzinfo=timezone.utc),
    )
    claims = await repository.claim(
        now=datetime(2030, 1, 1, 3, 0, 30, tzinfo=timezone.utc),
        limit=10,
    )
    completed = await repository.complete(
        delivery_id=DELIVERY_ID,
        claim_token=CLAIM_TOKEN,
        outcome=ReminderDispatchOutcome.SENT,
    )

    assert count == 2
    assert claims[0].delivery_id == DELIVERY_ID
    assert claims[0].claim_token == CLAIM_TOKEN
    assert completed.status.value == "sent"
    assert not hasattr(completed, "claim_token")

    await client.aclose()
