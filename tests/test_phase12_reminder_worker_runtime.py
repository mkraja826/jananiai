import asyncio
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.notifications.models import (
    NotificationDestination,
    NotificationPlatform,
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
from app.workers.models import ReminderWorkerRunState
from app.workers.runtime import ReminderWorkerRuntime

RUN_AT = datetime(2030, 1, 2, 6, 30, tzinfo=UTC)
CLAIM_TOKEN = UUID("00000000-0000-0000-0000-000000001201")


def make_claim(index: int) -> ReminderDispatchClaim:
    return ReminderDispatchClaim(
        delivery_id=UUID(f"00000000-0000-0000-0000-{1200 + index:012d}"),
        reminder_kind=ReminderKind.MEDICATION,
        medication_reminder_id=UUID(f"00000000-0000-0000-0000-{2200 + index:012d}"),
        scheduled_for=RUN_AT - timedelta(minutes=1),
        status=ReminderDeliveryStatus.CLAIMED,
        attempt_count=1,
        claim_token=CLAIM_TOKEN,
        claimed_at=RUN_AT - timedelta(seconds=5),
    )


class FakeQueue:
    def __init__(self, claims: list[ReminderDispatchClaim]) -> None:
        self.claims = claims
        self.materializations: list[tuple[datetime, datetime]] = []
        self.completions: list[dict[str, object]] = []
        self.fail_runtime_requeue = False

    async def materialize(self, *, window_start: datetime, window_end: datetime) -> int:
        self.materializations.append((window_start, window_end))
        return 4

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
        if self.fail_runtime_requeue and failure_code == "worker_runtime_error":
            raise RuntimeError("synthetic persistence outage")
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
            medication_reminder_id=UUID("00000000-0000-0000-0000-000000009999"),
            scheduled_for=RUN_AT,
            status=status,
            attempt_count=1,
        )


class FakeDestinations:
    def __init__(self, tokens: dict[UUID, str], *, fail_delivery_id: UUID | None = None) -> None:
        self._tokens = tokens
        self._fail_delivery_id = fail_delivery_id

    async def destinations_for_claim(
        self,
        *,
        delivery_id: UUID,
        claim_token: UUID,
    ) -> list[NotificationDestination]:
        if delivery_id == self._fail_delivery_id:
            raise RuntimeError("synthetic destination outage")
        token = self._tokens.get(delivery_id)
        if token is None:
            return []
        return [
            NotificationDestination(
                device_id=UUID("00000000-0000-0000-0000-000000008888"),
                platform=NotificationPlatform.ANDROID,
                transport=NotificationTransportKind.MOCK,
                push_token=token,
            )
        ]


def run_runtime(
    queue: FakeQueue,
    destinations: FakeDestinations,
    *,
    now: datetime = RUN_AT,
    batch_size: int = 50,
):
    runtime = ReminderWorkerRuntime(
        queue=queue,
        destinations=destinations,
        transport=MockNotificationTransport(),
        batch_size=batch_size,
        lookback_minutes=15,
        horizon_minutes=1440,
    )
    return asyncio.run(runtime.run_once(now=now))


def test_run_once_materializes_bounded_window_and_aggregates_job_outcomes() -> None:
    claims = [make_claim(1), make_claim(2), make_claim(3)]
    queue = FakeQueue(claims)
    destinations = FakeDestinations(
        {
            claims[0].delivery_id: "mock-success:device-a",
            claims[1].delivery_id: "mock-retry:device-b",
            claims[2].delivery_id: "mock-terminal:device-c",
        }
    )

    report = run_runtime(queue, destinations)

    assert report.state is ReminderWorkerRunState.COMPLETED
    assert report.materialization_window_start == RUN_AT - timedelta(minutes=15)
    assert report.materialization_window_end == RUN_AT + timedelta(minutes=1440)
    assert queue.materializations == [
        (RUN_AT - timedelta(minutes=15), RUN_AT + timedelta(minutes=1440))
    ]
    assert report.materialized_job_count == 4
    assert report.claimed_job_count == 3
    assert report.sent_job_count == 1
    assert report.retryable_job_count == 1
    assert report.terminal_job_count == 1
    assert report.runtime_error_job_count == 0
    assert report.requeue_failure_job_count == 0


def test_single_destination_infrastructure_failure_requeues_and_does_not_abort_batch() -> None:
    failed_claim = make_claim(4)
    good_claim = make_claim(5)
    queue = FakeQueue([failed_claim, good_claim])
    destinations = FakeDestinations(
        {good_claim.delivery_id: "mock-success:device-good"},
        fail_delivery_id=failed_claim.delivery_id,
    )

    report = run_runtime(queue, destinations)

    assert report.state is ReminderWorkerRunState.DEGRADED
    assert report.claimed_job_count == 2
    assert report.sent_job_count == 1
    assert report.runtime_error_job_count == 1
    assert report.requeue_failure_job_count == 0
    runtime_requeues = [
        item for item in queue.completions if item["failure_code"] == "worker_runtime_error"
    ]
    assert len(runtime_requeues) == 1
    assert runtime_requeues[0]["delivery_id"] == failed_claim.delivery_id
    assert runtime_requeues[0]["outcome"] is ReminderDispatchOutcome.RETRYABLE_FAILURE


def test_failed_runtime_requeue_is_reported_without_exposing_exception_content() -> None:
    failed_claim = make_claim(6)
    queue = FakeQueue([failed_claim])
    queue.fail_runtime_requeue = True
    destinations = FakeDestinations({}, fail_delivery_id=failed_claim.delivery_id)

    report = run_runtime(queue, destinations)
    serialized = report.model_dump_json()

    assert report.state is ReminderWorkerRunState.DEGRADED
    assert report.runtime_error_job_count == 1
    assert report.requeue_failure_job_count == 1
    assert "synthetic destination outage" not in serialized
    assert "synthetic persistence outage" not in serialized
    assert str(failed_claim.delivery_id) not in serialized


def test_worker_normalizes_timezone_aware_clock_to_utc() -> None:
    offset_clock = datetime(2030, 1, 2, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    queue = FakeQueue([])
    destinations = FakeDestinations({})

    report = run_runtime(queue, destinations, now=offset_clock)

    assert report.run_at == RUN_AT
    assert queue.materializations[0][0] == RUN_AT - timedelta(minutes=15)


def test_worker_rejects_naive_clock_before_touching_queue() -> None:
    queue = FakeQueue([])
    destinations = FakeDestinations({})

    with pytest.raises(ValueError, match="timezone-aware"):
        run_runtime(queue, destinations, now=datetime(2030, 1, 2, 6, 30))

    assert queue.materializations == []


def test_worker_respects_batch_size_without_claiming_unbounded_jobs() -> None:
    claims = [make_claim(index) for index in range(10, 15)]
    queue = FakeQueue(claims)
    destinations = FakeDestinations({claim.delivery_id: "mock-success:device" for claim in claims})

    report = run_runtime(queue, destinations, batch_size=2)

    assert report.claimed_job_count == 2
    assert report.sent_job_count == 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"batch_size": 0}, "batch_size"),
        ({"batch_size": 101}, "batch_size"),
        ({"lookback_minutes": -1}, "lookback_minutes"),
        ({"lookback_minutes": 1441}, "lookback_minutes"),
        ({"horizon_minutes": 0}, "horizon_minutes"),
        ({"horizon_minutes": 10081}, "horizon_minutes"),
    ],
)
def test_worker_runtime_rejects_unbounded_configuration(
    kwargs: dict[str, int],
    message: str,
) -> None:
    queue = FakeQueue([])
    destinations = FakeDestinations({})
    defaults = {
        "batch_size": 50,
        "lookback_minutes": 15,
        "horizon_minutes": 1440,
    }
    defaults.update(kwargs)

    with pytest.raises(ValueError, match=message):
        ReminderWorkerRuntime(
            queue=queue,
            destinations=destinations,
            transport=MockNotificationTransport(),
            **defaults,
        )
