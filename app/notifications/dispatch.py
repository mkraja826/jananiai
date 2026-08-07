from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.notifications.models import (
    NotificationDestination,
    NotificationTransportDisposition,
    ReminderNotificationDispatchResult,
)
from app.notifications.transport import NotificationTransport, build_generic_reminder_envelope
from app.reminders.models import (
    ReminderDelivery,
    ReminderDispatchClaim,
    ReminderDispatchOutcome,
)


class ReminderQueueWorker(Protocol):
    async def claim(
        self,
        *,
        now: datetime,
        limit: int = 50,
    ) -> list[ReminderDispatchClaim]: ...

    async def complete(
        self,
        *,
        delivery_id: UUID,
        claim_token: UUID,
        outcome: ReminderDispatchOutcome,
        now: datetime,
        failure_code: str | None = None,
    ) -> ReminderDelivery: ...


class NotificationDestinationWorker(Protocol):
    async def destinations_for_claim(
        self,
        *,
        delivery_id: UUID,
        claim_token: UUID,
    ) -> list[NotificationDestination]: ...


class ReminderNotificationDispatcher:
    """Dispatch claimed reminder jobs using generic non-clinical notification content."""

    def __init__(
        self,
        *,
        queue: ReminderQueueWorker,
        destinations: NotificationDestinationWorker,
        transport: NotificationTransport,
    ) -> None:
        self._queue = queue
        self._destinations = destinations
        self._transport = transport

    async def dispatch_due(
        self,
        *,
        now: datetime,
        limit: int = 50,
    ) -> list[ReminderNotificationDispatchResult]:
        claims = await self._queue.claim(now=now, limit=max(1, min(limit, 100)))
        results: list[ReminderNotificationDispatchResult] = []
        for claim in claims:
            results.append(await self.dispatch_claim(claim=claim, now=now))
        return results

    async def dispatch_claim(
        self,
        *,
        claim: ReminderDispatchClaim,
        now: datetime,
    ) -> ReminderNotificationDispatchResult:
        destinations = await self._destinations.destinations_for_claim(
            delivery_id=claim.delivery_id,
            claim_token=claim.claim_token,
        )
        if not destinations:
            await self._queue.complete(
                delivery_id=claim.delivery_id,
                claim_token=claim.claim_token,
                outcome=ReminderDispatchOutcome.RETRYABLE_FAILURE,
                now=now,
                failure_code="no_active_destination",
            )
            return ReminderNotificationDispatchResult(
                delivery_id=claim.delivery_id,
                disposition=NotificationTransportDisposition.RETRYABLE_FAILURE,
                destination_count=0,
                sent_count=0,
                retryable_failure_count=0,
                terminal_failure_count=0,
            )

        envelope = build_generic_reminder_envelope(claim.delivery_id)
        transport_results = []
        for destination in destinations:
            transport_results.append(await self._transport.send(destination, envelope))

        sent_count = sum(
            item.disposition is NotificationTransportDisposition.SENT for item in transport_results
        )
        retryable_count = sum(
            item.disposition is NotificationTransportDisposition.RETRYABLE_FAILURE
            for item in transport_results
        )
        terminal_count = sum(
            item.disposition is NotificationTransportDisposition.TERMINAL_FAILURE
            for item in transport_results
        )

        if sent_count:
            disposition = NotificationTransportDisposition.SENT
            queue_outcome = ReminderDispatchOutcome.SENT
            failure_code = None
        elif retryable_count:
            disposition = NotificationTransportDisposition.RETRYABLE_FAILURE
            queue_outcome = ReminderDispatchOutcome.RETRYABLE_FAILURE
            failure_code = "notification_destination_retryable"
        else:
            disposition = NotificationTransportDisposition.TERMINAL_FAILURE
            queue_outcome = ReminderDispatchOutcome.TERMINAL_FAILURE
            failure_code = "all_notification_destinations_terminal"

        await self._queue.complete(
            delivery_id=claim.delivery_id,
            claim_token=claim.claim_token,
            outcome=queue_outcome,
            now=now,
            failure_code=failure_code,
        )
        return ReminderNotificationDispatchResult(
            delivery_id=claim.delivery_id,
            disposition=disposition,
            destination_count=len(destinations),
            sent_count=sent_count,
            retryable_failure_count=retryable_count,
            terminal_failure_count=terminal_count,
        )
