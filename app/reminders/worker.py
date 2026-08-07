from datetime import datetime
from uuid import UUID

import httpx

from app.reminders.models import (
    ReminderDelivery,
    ReminderDeliveryOrigin,
    ReminderDeliveryStatus,
    ReminderDispatchClaim,
    ReminderDispatchOutcome,
    ReminderKind,
)


class ReminderDeliveryWorkerError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class SupabaseReminderDeliveryWorkerRepository:
    """Service-role-only queue operations; it does not send push notifications itself."""

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        timeout_seconds: float = 8.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not service_role_key.strip():
            raise ValueError("Service-role key is required")
        self._supabase_url = supabase_url.rstrip("/")
        self._service_role_key = service_role_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def materialize(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        payload = await self._rpc(
            "materialize_janani_reminder_deliveries",
            {
                "p_window_start": window_start.isoformat(),
                "p_window_end": window_end.isoformat(),
            },
        )
        if not isinstance(payload, int):
            raise ReminderDeliveryWorkerError("Reminder materialization returned an invalid count")
        return payload

    async def claim(
        self,
        *,
        now: datetime,
        limit: int = 50,
    ) -> list[ReminderDispatchClaim]:
        payload = await self._rpc(
            "claim_janani_reminder_deliveries",
            {"p_now": now.isoformat(), "p_limit": max(1, min(limit, 100))},
        )
        if not isinstance(payload, list):
            raise ReminderDeliveryWorkerError("Reminder claim RPC returned an invalid response")
        return [self._map_claim(item) for item in payload]

    async def complete(
        self,
        *,
        delivery_id: UUID,
        claim_token: UUID,
        outcome: ReminderDispatchOutcome,
        failure_code: str | None = None,
    ) -> ReminderDelivery:
        payload = await self._rpc(
            "complete_janani_reminder_delivery",
            {
                "p_delivery_id": str(delivery_id),
                "p_claim_token": str(claim_token),
                "p_outcome": outcome.value,
                "p_failure_code": failure_code,
            },
        )
        if not isinstance(payload, dict):
            raise ReminderDeliveryWorkerError("Reminder completion RPC returned an invalid job")
        return self._map_delivery(payload)

    async def _rpc(self, function_name: str, payload: dict[str, object]) -> object:
        try:
            response = await self._client.post(
                f"{self._supabase_url}/rest/v1/rpc/{function_name}",
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                    "Content-Type": "application/json",
                    "Accept-Profile": "public",
                    "Content-Profile": "public",
                },
                json=payload,
            )
        except httpx.RequestError as exc:
            raise ReminderDeliveryWorkerError(
                "Reminder delivery persistence could not be reached"
            ) from exc

        if response.status_code in {401, 403}:
            raise ReminderDeliveryWorkerError(
                "Reminder delivery worker operation was denied",
                status_code=403,
            )
        if response.status_code == 404:
            raise ReminderDeliveryWorkerError(
                "Reminder delivery worker RPC was not found",
                status_code=404,
            )
        if response.status_code >= 500:
            raise ReminderDeliveryWorkerError(
                "Reminder delivery persistence failed",
                status_code=502,
            )
        if response.status_code >= 400:
            raise ReminderDeliveryWorkerError(
                "Reminder delivery worker operation was rejected",
                status_code=400,
            )
        if not response.content:
            return None
        return response.json()

    def _map_claim(self, row: object) -> ReminderDispatchClaim:
        if not isinstance(row, dict):
            raise ReminderDeliveryWorkerError("Reminder claim contained an invalid job")
        return ReminderDispatchClaim(
            **self._delivery_fields(row),
            claim_token=UUID(row["claim_token"]),
            claimed_at=row["claimed_at"],
        )

    def _map_delivery(self, row: dict) -> ReminderDelivery:
        return ReminderDelivery(**self._delivery_fields(row))

    def _delivery_fields(self, row: dict) -> dict[str, object]:
        return {
            "delivery_id": UUID(row["id"]),
            "reminder_kind": ReminderKind(row["reminder_kind"]),
            "medication_reminder_id": (
                UUID(row["medication_reminder_id"])
                if row.get("medication_reminder_id")
                else None
            ),
            "appointment_reminder_id": (
                UUID(row["appointment_reminder_id"])
                if row.get("appointment_reminder_id")
                else None
            ),
            "scheduled_for": row["scheduled_for"],
            "origin": ReminderDeliveryOrigin(row.get("origin", "schedule")),
            "status": ReminderDeliveryStatus(row["status"]),
            "attempt_count": int(row.get("attempt_count", 0)),
            "synthetic": bool(row.get("synthetic", True)),
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        }
