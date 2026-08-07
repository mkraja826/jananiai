import asyncio
from typing import Protocol
from uuid import UUID

from app.auth.models import AuthenticatedUser
from app.persistence.client import SupabasePersistenceError, SupabaseUserRestClient
from app.reminders.models import (
    AppointmentReminderSchedule,
    AppointmentReminderScheduleCreate,
    MedicationReminderSchedule,
    MedicationReminderScheduleCreate,
    ReminderDelivery,
    ReminderDeliveryOrigin,
    ReminderDeliveryOverview,
    ReminderDeliveryStatus,
    ReminderKind,
    ReminderOverview,
    ReminderResponse,
    ReminderResponseCreate,
)


class ReminderRepository(Protocol):
    async def list_reminders(self, user: AuthenticatedUser) -> ReminderOverview: ...

    async def create_medication_reminder(
        self,
        user: AuthenticatedUser,
        payload: MedicationReminderScheduleCreate,
    ) -> MedicationReminderSchedule: ...

    async def create_appointment_reminder(
        self,
        user: AuthenticatedUser,
        payload: AppointmentReminderScheduleCreate,
    ) -> AppointmentReminderSchedule: ...

    async def disable_medication_reminder(
        self,
        user: AuthenticatedUser,
        reminder_id: UUID,
    ) -> MedicationReminderSchedule: ...

    async def disable_appointment_reminder(
        self,
        user: AuthenticatedUser,
        reminder_id: UUID,
    ) -> AppointmentReminderSchedule: ...

    async def list_deliveries(
        self,
        user: AuthenticatedUser,
        *,
        limit: int = 100,
    ) -> ReminderDeliveryOverview: ...

    async def record_response(
        self,
        user: AuthenticatedUser,
        delivery_id: UUID,
        payload: ReminderResponseCreate,
    ) -> ReminderResponse: ...


class SupabaseReminderRepository:
    """Persist explicit user reminder choices without inferring medication advice."""

    def __init__(self, client: SupabaseUserRestClient) -> None:
        self._client = client

    async def list_reminders(self, user: AuthenticatedUser) -> ReminderOverview:
        self._ensure_identity(user)
        medication_rows, appointment_rows = await asyncio.gather(
            self._client.select(
                "medication_reminder_schedules",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "order": "created_at.desc",
                    "limit": "200",
                },
            ),
            self._client.select(
                "appointment_reminder_schedules",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "order": "created_at.desc",
                    "limit": "200",
                },
            ),
        )
        return ReminderOverview(
            medication_reminders=[self._map_medication(row) for row in medication_rows],
            appointment_reminders=[self._map_appointment(row) for row in appointment_rows],
        )

    async def create_medication_reminder(
        self,
        user: AuthenticatedUser,
        payload: MedicationReminderScheduleCreate,
    ) -> MedicationReminderSchedule:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "create_janani_medication_reminder",
            {
                "p_medication_id": str(payload.medication_id),
                "p_local_time": payload.local_time.isoformat(),
                "p_timezone_name": payload.timezone_name,
                "p_start_date": payload.start_date.isoformat(),
                "p_end_date": payload.end_date.isoformat() if payload.end_date else None,
                "p_weekdays": payload.weekdays,
                "p_synthetic": payload.synthetic,
            },
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Reminder RPC returned an invalid medication schedule")
        return self._map_medication(data)

    async def create_appointment_reminder(
        self,
        user: AuthenticatedUser,
        payload: AppointmentReminderScheduleCreate,
    ) -> AppointmentReminderSchedule:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "create_janani_appointment_reminder",
            {
                "p_appointment_id": str(payload.appointment_id),
                "p_lead_minutes": payload.lead_minutes,
                "p_synthetic": payload.synthetic,
            },
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Reminder RPC returned an invalid appointment schedule")
        return self._map_appointment(data)

    async def disable_medication_reminder(
        self,
        user: AuthenticatedUser,
        reminder_id: UUID,
    ) -> MedicationReminderSchedule:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "disable_janani_reminder",
            {"p_reminder_kind": "medication", "p_reminder_id": str(reminder_id)},
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Reminder RPC returned an invalid medication schedule")
        return self._map_medication(data)

    async def disable_appointment_reminder(
        self,
        user: AuthenticatedUser,
        reminder_id: UUID,
    ) -> AppointmentReminderSchedule:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "disable_janani_reminder",
            {"p_reminder_kind": "appointment", "p_reminder_id": str(reminder_id)},
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Reminder RPC returned an invalid appointment schedule")
        return self._map_appointment(data)

    async def list_deliveries(
        self,
        user: AuthenticatedUser,
        *,
        limit: int = 100,
    ) -> ReminderDeliveryOverview:
        self._ensure_identity(user)
        safe_limit = max(1, min(limit, 200))
        rows = await self._client.select(
            "reminder_delivery_jobs",
            params={
                "select": (
                    "id,reminder_kind,medication_reminder_id,appointment_reminder_id,"
                    "scheduled_for,origin,status,attempt_count,synthetic,created_at,completed_at"
                ),
                "user_id": f"eq.{user.user_id}",
                "order": "scheduled_for.desc",
                "limit": str(safe_limit),
            },
        )
        return ReminderDeliveryOverview(deliveries=[self._map_delivery(row) for row in rows])

    async def record_response(
        self,
        user: AuthenticatedUser,
        delivery_id: UUID,
        payload: ReminderResponseCreate,
    ) -> ReminderResponse:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "record_janani_reminder_response",
            {
                "p_client_event_id": str(payload.client_event_id),
                "p_delivery_id": str(delivery_id),
                "p_event_type": payload.event_type.value,
                "p_occurred_at": payload.occurred_at.isoformat(),
                "p_remind_at": payload.remind_at.isoformat() if payload.remind_at else None,
                "p_synthetic": payload.synthetic,
            },
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Reminder response RPC returned an invalid event")
        return self._map_response(data)

    def _map_medication(self, row: dict) -> MedicationReminderSchedule:
        return MedicationReminderSchedule(
            reminder_id=UUID(row["id"]),
            medication_id=UUID(row["medication_id"]),
            local_time=row["local_time"],
            timezone_name=row["timezone_name"],
            start_date=row["start_date"],
            end_date=row.get("end_date"),
            weekdays=row.get("weekdays") or [1, 2, 3, 4, 5, 6, 7],
            enabled=bool(row.get("enabled", True)),
            created_at=row.get("created_at"),
            disabled_at=row.get("disabled_at"),
            synthetic=bool(row.get("synthetic", True)),
        )

    def _map_appointment(self, row: dict) -> AppointmentReminderSchedule:
        return AppointmentReminderSchedule(
            reminder_id=UUID(row["id"]),
            appointment_id=UUID(row["appointment_id"]),
            lead_minutes=row["lead_minutes"],
            enabled=bool(row.get("enabled", True)),
            created_at=row.get("created_at"),
            disabled_at=row.get("disabled_at"),
            synthetic=bool(row.get("synthetic", True)),
        )

    def _map_delivery(self, row: dict) -> ReminderDelivery:
        return ReminderDelivery(
            delivery_id=UUID(row["id"]),
            reminder_kind=ReminderKind(row["reminder_kind"]),
            medication_reminder_id=(
                UUID(row["medication_reminder_id"]) if row.get("medication_reminder_id") else None
            ),
            appointment_reminder_id=(
                UUID(row["appointment_reminder_id"]) if row.get("appointment_reminder_id") else None
            ),
            scheduled_for=row["scheduled_for"],
            origin=ReminderDeliveryOrigin(row.get("origin", "schedule")),
            status=ReminderDeliveryStatus(row["status"]),
            attempt_count=int(row.get("attempt_count", 0)),
            synthetic=bool(row.get("synthetic", True)),
            created_at=row.get("created_at"),
            completed_at=row.get("completed_at"),
        )

    def _map_response(self, row: dict) -> ReminderResponse:
        return ReminderResponse(
            response_id=UUID(row["id"]),
            delivery_id=UUID(row["delivery_id"]),
            client_event_id=UUID(row["client_event_id"]),
            event_type=row["event_type"],
            occurred_at=row["occurred_at"],
            remind_at=row.get("remind_at"),
            synthetic=bool(row.get("synthetic", True)),
            created_at=row.get("created_at"),
        )

    def _ensure_identity(self, user: AuthenticatedUser) -> None:
        if user.user_id != self._client.user.user_id:
            raise ValueError("Repository identity does not match the authenticated user")
