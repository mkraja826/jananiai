from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.reminders.dependencies import get_reminder_repository
from app.reminders.models import (
    ReminderDelivery,
    ReminderDeliveryOverview,
    ReminderDeliveryStatus,
    ReminderKind,
    ReminderResponse,
    ReminderResponseCreate,
)

DELIVERY_ID = UUID("00000000-0000-0000-0000-000000001011")
REMINDER_ID = UUID("00000000-0000-0000-0000-000000001012")
EVENT_ID = UUID("00000000-0000-0000-0000-000000001013")


class FakeReminderDeliveryRepository:
    async def list_deliveries(self, user, *, limit: int = 100) -> ReminderDeliveryOverview:
        return ReminderDeliveryOverview(
            deliveries=[
                ReminderDelivery(
                    delivery_id=DELIVERY_ID,
                    reminder_kind=ReminderKind.MEDICATION,
                    medication_reminder_id=REMINDER_ID,
                    scheduled_for=datetime(2030, 1, 1, 3, 0, tzinfo=UTC),
                    status=ReminderDeliveryStatus.SENT,
                    attempt_count=1,
                )
            ][:limit]
        )

    async def record_response(
        self,
        user,
        delivery_id: UUID,
        payload: ReminderResponseCreate,
    ) -> ReminderResponse:
        return ReminderResponse(
            response_id=UUID("00000000-0000-0000-0000-000000001014"),
            delivery_id=delivery_id,
            **payload.model_dump(),
        )


def client() -> TestClient:
    application = create_app(settings=Settings(environment="test", free_first_mode=True))
    application.dependency_overrides[get_reminder_repository] = lambda: (
        FakeReminderDeliveryRepository()
    )
    return TestClient(application)


def test_list_delivery_api_returns_neutral_queue_metadata() -> None:
    response = client().get("/v1/reminders/deliveries?limit=20")

    assert response.status_code == 200
    payload = response.json()["deliveries"][0]
    assert payload["delivery_id"] == str(DELIVERY_ID)
    assert payload["reminder_kind"] == "medication"
    assert "claim_token" not in payload
    assert "failure_code" not in payload
    assert "medication_name" not in payload


def test_response_api_records_explicit_remind_later_time() -> None:
    response = client().post(
        f"/v1/reminders/deliveries/{DELIVERY_ID}/responses",
        json={
            "client_event_id": str(EVENT_ID),
            "event_type": "remind_later",
            "occurred_at": "2030-01-01T03:05:00Z",
            "remind_at": "2030-01-01T04:00:00Z",
            "synthetic": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["event_type"] == "remind_later"
    assert response.json()["remind_at"] == "2030-01-01T04:00:00Z"


def test_real_response_payload_is_blocked_in_free_first_mode() -> None:
    response = client().post(
        f"/v1/reminders/deliveries/{DELIVERY_ID}/responses",
        json={
            "client_event_id": str(EVENT_ID),
            "event_type": "acknowledged",
            "occurred_at": "2030-01-01T03:05:00Z",
            "synthetic": False,
        },
    )

    assert response.status_code == 403
    assert "Real patient data" in response.json()["detail"]


def test_delivery_list_limit_is_bounded() -> None:
    response = client().get("/v1/reminders/deliveries?limit=201")

    assert response.status_code == 422
