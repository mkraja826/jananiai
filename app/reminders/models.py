from datetime import date, datetime, time
from enum import StrEnum
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator


class MedicationReminderScheduleCreate(BaseModel):
    medication_id: UUID
    local_time: time
    timezone_name: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date | None = None
    weekdays: list[Annotated[int, Field(ge=1, le=7)]] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5, 6, 7],
        min_length=1,
        max_length=7,
    )
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_schedule(self) -> "MedicationReminderScheduleCreate":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("weekdays cannot contain duplicates")
        try:
            ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone_name must be a valid IANA timezone") from exc
        return self


class MedicationReminderSchedule(MedicationReminderScheduleCreate):
    reminder_id: UUID
    enabled: bool = True
    created_at: datetime | None = None
    disabled_at: datetime | None = None


class AppointmentReminderScheduleCreate(BaseModel):
    appointment_id: UUID
    lead_minutes: Annotated[int, Field(ge=0, le=43_200)]
    synthetic: bool = True


class AppointmentReminderSchedule(AppointmentReminderScheduleCreate):
    reminder_id: UUID
    enabled: bool = True
    created_at: datetime | None = None
    disabled_at: datetime | None = None


class ReminderOverview(BaseModel):
    medication_reminders: list[MedicationReminderSchedule] = Field(default_factory=list)
    appointment_reminders: list[AppointmentReminderSchedule] = Field(default_factory=list)


class ReminderKind(StrEnum):
    MEDICATION = "medication"
    APPOINTMENT = "appointment"


class ReminderDeliveryOrigin(StrEnum):
    SCHEDULE = "schedule"
    REMIND_LATER = "remind_later"


class ReminderDeliveryStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderDelivery(BaseModel):
    delivery_id: UUID
    reminder_kind: ReminderKind
    medication_reminder_id: UUID | None = None
    appointment_reminder_id: UUID | None = None
    scheduled_for: datetime
    origin: ReminderDeliveryOrigin = ReminderDeliveryOrigin.SCHEDULE
    status: ReminderDeliveryStatus
    attempt_count: int = Field(ge=0, le=5)
    synthetic: bool = True
    created_at: datetime | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_reminder_reference(self) -> "ReminderDelivery":
        medication_selected = self.medication_reminder_id is not None
        appointment_selected = self.appointment_reminder_id is not None
        if medication_selected == appointment_selected:
            raise ValueError("exactly one reminder schedule reference is required")
        if self.reminder_kind is ReminderKind.MEDICATION and not medication_selected:
            raise ValueError("medication delivery requires medication_reminder_id")
        if self.reminder_kind is ReminderKind.APPOINTMENT and not appointment_selected:
            raise ValueError("appointment delivery requires appointment_reminder_id")
        return self


class ReminderDeliveryOverview(BaseModel):
    deliveries: list[ReminderDelivery] = Field(default_factory=list)


class ReminderResponseType(StrEnum):
    OPENED = "opened"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"
    REMIND_LATER = "remind_later"


class ReminderResponseCreate(BaseModel):
    client_event_id: UUID
    event_type: ReminderResponseType
    occurred_at: datetime
    remind_at: datetime | None = None
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_response(self) -> "ReminderResponseCreate":
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        if self.event_type is ReminderResponseType.REMIND_LATER:
            if self.remind_at is None:
                raise ValueError("remind_later requires an explicit remind_at time")
            if self.remind_at.tzinfo is None or self.remind_at.utcoffset() is None:
                raise ValueError("remind_at must include a timezone")
            if self.remind_at <= self.occurred_at:
                raise ValueError("remind_at must be later than occurred_at")
        elif self.remind_at is not None:
            raise ValueError("remind_at is allowed only for remind_later events")
        return self


class ReminderResponse(ReminderResponseCreate):
    response_id: UUID
    delivery_id: UUID
    created_at: datetime | None = None


class ReminderDispatchClaim(ReminderDelivery):
    claim_token: UUID
    claimed_at: datetime


class ReminderDispatchOutcome(StrEnum):
    SENT = "sent"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
