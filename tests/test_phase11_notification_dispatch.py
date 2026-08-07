import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.notifications.dispatch import ReminderNotificationDispatcher
from app.notifications.models import (
    NotificationDestination,
    NotificationPlatform,
    NotificationTransportDisposition,
    NotificationTransportKind,
)
from app.notifications.transport import MockNotificationTransport
from app.reminders.models import (
    ReminderDelivery,
    ReminderDeliveryStatus,
    ReminderDispatchClaim,
    ReminderDispatchOutcome,
    ReminderKind,
)

DELIVERY_ID = UUID("00000000-0000-0000-0000-000000001121")
REMINDER_ID = UUID("00000000-0000-0000-0000-000000001122")
CLAIM_TOKEN = UUID("00000000-0000-0000-0000-000000001123")
NOW = datetime(2030, 1, 1, 3, 0, 31, tzinfo=UTC)


def claim() -> ReminderDispatchClaim:
    return ReminderDispatchClaim(
        delivery_id=DELIVERY_ID,
        reminder_kind=ReminderKind.MEDICATION,
        medication_reminder_id=REMINDER_ID,
        scheduled_for=datetime(2030, 1, 1, 3, 0, tzinfo=UTC),
        status=ReminderDeliveryStatus.CLAIMED,
        attempt_count=1,
        claim_token=CLAIM_TOKEN,
        claimed_at=datetime(2030, 1, 1, 3, 0, 30, tzinfo=UTC),
    )


class FakeQueue:
    def __init__(self) -> None:
        self.claims = [claim()]
        self.completions: list[dict[str, object]] = []

    async def claim(self, *, now: datetime, limit: int = 50) -> list[ReminderDispatchClaim]:
        return self.claims[:limit]

    async def complete(
        self,
        *,
        delivery_id: UUID,
        claim_token: UUID,
        outcome: ReminderDispatchOutcome,
        now: datetime,
        failure_code: str | None = None,
    ) -> ReminderDelivery:
        self.completions.append(
            {
                "delivery_id": delivery_id,
                "claim_token": claim_token,
                "outcome": outcome,
                "now": now,
                "failure_code": failure_code,
            }
        )
        status = (
            ReminderDeliveryStatus.SENT
            if outcome is ReminderDispatchOutcome.SENT
            else (
                ReminderDeliveryStatus.PENDING
                if outcome is ReminderDispatchOutcome.RETRYABLE_FAILURE
                else ReminderDeliveryStatus.FAILED
            )
        )
        return ReminderDelivery(
            delivery_id=delivery_id,
            reminder_kind=ReminderKind.MEDICATION,
            medication_reminder_id=REMINDER_ID,
            scheduled_for=datetime(2030, 1, 1, 3, 0, tzinfo=UTC),
            status=status,
            attempt_count=1,
        )


class FakeDestinations:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self.requests: list[tuple[UUID, UUID]] = []

    async def destinations_for_claim(
        self,
        *,
        delivery_id: UUID,
        claim_token: UUID,
    ) -> list[NotificationDestination]:
        self.requests.append((delivery_id, claim_token))
        return [
            NotificationDestination(
                device_id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
                platform=NotificationPlatform.ANDROID,
                transport=NotificationTransportKind.MOCK,
                push_token=token,
            )
            for index, token in enumerate(self._tokens, start=1)
        ]


def run_dispatch(tokens: list[str]):
    async def run():
        queue = FakeQueue()
        destinations = FakeDestinations(tokens)
        dispatcher = ReminderNotificationDispatcher(
            queue=queue,
            destinations=destinations,
            transport=MockNotificationTransport(),
        )
        result = await dispatcher.dispatch_claim(claim=claim(), now=NOW)
        return result, queue, destinations

    return asyncio.run(run())


def test_success_on_any_destination_completes_job_as_sent() -> None:
    result, queue, destinations = run_dispatch(
        ["mock-terminal:bad-token", "mock-success:good-token"]
    )

    assert result.disposition is NotificationTransportDisposition.SENT
    assert result.destination_count == 2
    assert result.sent_count == 1
    assert result.terminal_failure_count == 1
    assert destinations.requests == [(DELIVERY_ID, CLAIM_TOKEN)]
    assert queue.completions[0]["outcome"] is ReminderDispatchOutcome.SENT
    assert queue.completions[0]["failure_code"] is None


def test_no_active_destination_uses_bounded_retryable_queue_outcome() -> None:
    result, queue, _ = run_dispatch([])

    assert result.disposition is NotificationTransportDisposition.RETRYABLE_FAILURE
    assert result.destination_count == 0
    assert queue.completions[0]["outcome"] is ReminderDispatchOutcome.RETRYABLE_FAILURE
    assert queue.completions[0]["failure_code"] == "no_active_destination"


def test_any_retryable_destination_keeps_job_retryable_when_none_sent() -> None:
    result, queue, _ = run_dispatch(
        ["mock-terminal:bad-token", "mock-retry:temporary-token"]
    )

    assert result.disposition is NotificationTransportDisposition.RETRYABLE_FAILURE
    assert result.retryable_failure_count == 1
    assert result.terminal_failure_count == 1
    assert queue.completions[0]["outcome"] is ReminderDispatchOutcome.RETRYABLE_FAILURE
    assert queue.completions[0]["failure_code"] == "notification_destination_retryable"


def test_all_terminal_destinations_fail_job_terminally() -> None:
    result, queue, _ = run_dispatch(
        ["mock-terminal:first", "mock-terminal:second"]
    )

    assert result.disposition is NotificationTransportDisposition.TERMINAL_FAILURE
    assert result.terminal_failure_count == 2
    assert queue.completions[0]["outcome"] is ReminderDispatchOutcome.TERMINAL_FAILURE
    assert queue.completions[0]["failure_code"] == "all_notification_destinations_terminal"


def test_dispatch_due_claims_and_dispatches_without_materializing_new_clinical_data() -> None:
    async def run() -> None:
        queue = FakeQueue()
        destinations = FakeDestinations(["mock-success:good-token"])
        dispatcher = ReminderNotificationDispatcher(
            queue=queue,
            destinations=destinations,
            transport=MockNotificationTransport(),
        )

        results = await dispatcher.dispatch_due(now=NOW, limit=5)

        assert len(results) == 1
        assert results[0].delivery_id == DELIVERY_ID
        assert queue.completions[0]["outcome"] is ReminderDispatchOutcome.SENT

    asyncio.run(run())
