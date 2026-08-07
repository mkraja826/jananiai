from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.config import Settings
from app.notifications.dispatch import ReminderNotificationDispatcher
from app.notifications.models import NotificationTransportDisposition
from app.notifications.transport import MockNotificationTransport, NotificationTransport
from app.notifications.worker import SupabaseNotificationWorkerRepository
from app.reminders.models import ReminderDispatchClaim, ReminderDispatchOutcome
from app.reminders.worker import SupabaseReminderDeliveryWorkerRepository
from app.workers.models import ReminderWorkerRunReport, ReminderWorkerRunState


class ReminderWorkerQueue(Protocol):
    async def materialize(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> int: ...

    async def claim(
        self,
        *,
        now: datetime,
        limit: int = 50,
    ) -> list[ReminderDispatchClaim]: ...

    async def complete(
        self,
        *,
        delivery_id,
        claim_token,
        outcome: ReminderDispatchOutcome,
        now: datetime,
        failure_code: str | None = None,
    ): ...


class ReminderWorkerConfigurationError(RuntimeError):
    pass


class ReminderWorkerRuntime:
    """Run one bounded reminder materialization and dispatch cycle."""

    def __init__(
        self,
        *,
        queue: ReminderWorkerQueue,
        destinations,
        transport: NotificationTransport,
        batch_size: int = 50,
        lookback_minutes: int = 15,
        horizon_minutes: int = 1440,
    ) -> None:
        if not 1 <= batch_size <= 100:
            raise ValueError("batch_size must be between 1 and 100")
        if not 0 <= lookback_minutes <= 1440:
            raise ValueError("lookback_minutes must be between 0 and 1440")
        if not 1 <= horizon_minutes <= 10080:
            raise ValueError("horizon_minutes must be between 1 and 10080")

        self._queue = queue
        self._batch_size = batch_size
        self._lookback = timedelta(minutes=lookback_minutes)
        self._horizon = timedelta(minutes=horizon_minutes)
        self._dispatcher = ReminderNotificationDispatcher(
            queue=queue,
            destinations=destinations,
            transport=transport,
        )

    async def run_once(self, *, now: datetime) -> ReminderWorkerRunReport:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Reminder worker clock must be timezone-aware")

        run_at = now.astimezone(UTC)
        window_start = run_at - self._lookback
        window_end = run_at + self._horizon

        materialized_count = await self._queue.materialize(
            window_start=window_start,
            window_end=window_end,
        )
        claims = await self._queue.claim(now=run_at, limit=self._batch_size)

        sent_count = 0
        retryable_count = 0
        terminal_count = 0
        runtime_error_count = 0
        requeue_failure_count = 0

        for claim in claims:
            try:
                result = await self._dispatcher.dispatch_claim(claim=claim, now=run_at)
            except Exception:
                runtime_error_count += 1
                try:
                    await self._queue.complete(
                        delivery_id=claim.delivery_id,
                        claim_token=claim.claim_token,
                        outcome=ReminderDispatchOutcome.RETRYABLE_FAILURE,
                        now=run_at,
                        failure_code="worker_runtime_error",
                    )
                except Exception:
                    requeue_failure_count += 1
                continue

            if result.disposition is NotificationTransportDisposition.SENT:
                sent_count += 1
            elif result.disposition is NotificationTransportDisposition.RETRYABLE_FAILURE:
                retryable_count += 1
            else:
                terminal_count += 1

        state = (
            ReminderWorkerRunState.DEGRADED
            if runtime_error_count or requeue_failure_count
            else ReminderWorkerRunState.COMPLETED
        )
        return ReminderWorkerRunReport(
            state=state,
            run_at=run_at,
            materialization_window_start=window_start,
            materialization_window_end=window_end,
            materialized_job_count=materialized_count,
            claimed_job_count=len(claims),
            sent_job_count=sent_count,
            retryable_job_count=retryable_count,
            terminal_job_count=terminal_count,
            runtime_error_job_count=runtime_error_count,
            requeue_failure_job_count=requeue_failure_count,
        )


async def run_configured_reminder_worker_once(
    settings: Settings,
    *,
    now: datetime | None = None,
) -> ReminderWorkerRunReport:
    """Create backend-only repositories, execute one cycle, and close all clients."""

    if not settings.reminder_worker_enabled:
        raise ReminderWorkerConfigurationError("Reminder worker is disabled")
    if not settings.supabase_worker_configured or settings.supabase_service_role_key is None:
        raise ReminderWorkerConfigurationError("Reminder worker backend configuration is incomplete")
    if settings.reminder_worker_transport != "mock":
        raise ReminderWorkerConfigurationError("Only the mock reminder transport is available")

    service_role_key = settings.supabase_service_role_key.get_secret_value()
    queue = SupabaseReminderDeliveryWorkerRepository(
        supabase_url=settings.normalized_supabase_url,
        service_role_key=service_role_key,
        timeout_seconds=settings.supabase_request_timeout_seconds,
    )
    destinations = SupabaseNotificationWorkerRepository(
        supabase_url=settings.normalized_supabase_url,
        service_role_key=service_role_key,
        timeout_seconds=settings.supabase_request_timeout_seconds,
    )
    runtime = ReminderWorkerRuntime(
        queue=queue,
        destinations=destinations,
        transport=MockNotificationTransport(),
        batch_size=settings.reminder_worker_batch_size,
        lookback_minutes=settings.reminder_worker_materialization_lookback_minutes,
        horizon_minutes=settings.reminder_worker_materialization_horizon_minutes,
    )

    try:
        return await runtime.run_once(now=now or datetime.now(UTC))
    finally:
        await destinations.aclose()
        await queue.aclose()
