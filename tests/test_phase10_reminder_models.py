from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.reminders.models import (
    ReminderDelivery,
    ReminderDeliveryStatus,
    ReminderKind,
    ReminderResponseCreate,
    ReminderResponseType,
)

DELIVERY_ID = UUID("00000000-0000-0000-0000-000000001001")
REMINDER_ID = UUID("00000000-0000-0000-0000-000000001002")
EVENT_ID = UUID("00000000-0000-0000-0000-000000001003")


def test_delivery_requires_exactly_one_matching_schedule_reference() -> None:
    delivery = ReminderDelivery(
        delivery_id=DELIVERY_ID,
        reminder_kind=ReminderKind.MEDICATION,
        medication_reminder_id=REMINDER_ID,
        scheduled_for=datetime(2030, 1, 1, 3, 0, tzinfo=UTC),
        status=ReminderDeliveryStatus.PENDING,
        attempt_count=0,
    )

    assert delivery.medication_reminder_id == REMINDER_ID
    assert delivery.appointment_reminder_id is None

    with pytest.raises(ValidationError):
        ReminderDelivery(
            delivery_id=DELIVERY_ID,
            reminder_kind=ReminderKind.MEDICATION,
            appointment_reminder_id=REMINDER_ID,
            scheduled_for=datetime(2030, 1, 1, 3, 0, tzinfo=UTC),
            status=ReminderDeliveryStatus.PENDING,
            attempt_count=0,
        )


def test_remind_later_requires_explicit_future_timezone_aware_time() -> None:
    response = ReminderResponseCreate(
        client_event_id=EVENT_ID,
        event_type=ReminderResponseType.REMIND_LATER,
        occurred_at=datetime(2030, 1, 1, 3, 5, tzinfo=UTC),
        remind_at=datetime(2030, 1, 1, 4, 0, tzinfo=UTC),
    )

    assert response.remind_at is not None

    with pytest.raises(ValidationError):
        ReminderResponseCreate(
            client_event_id=EVENT_ID,
            event_type=ReminderResponseType.REMIND_LATER,
            occurred_at=datetime(2030, 1, 1, 3, 5, tzinfo=UTC),
        )

    with pytest.raises(ValidationError):
        ReminderResponseCreate(
            client_event_id=EVENT_ID,
            event_type=ReminderResponseType.REMIND_LATER,
            occurred_at=datetime(2030, 1, 1, 3, 5),
            remind_at=datetime(2030, 1, 1, 4, 0),
        )


def test_neutral_response_contract_does_not_claim_medication_was_taken() -> None:
    assert {item.value for item in ReminderResponseType} == {
        "opened",
        "acknowledged",
        "dismissed",
        "remind_later",
    }
