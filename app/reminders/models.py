from datetime import date, datetime, time
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
