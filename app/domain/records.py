from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DietaryPreference(StrEnum):
    VEGETARIAN = "vegetarian"
    NON_VEGETARIAN = "non_vegetarian"
    VEGAN = "vegan"
    EGGETARIAN = "eggetarian"
    OTHER = "other"
    NOT_SPECIFIED = "not_specified"


class MedicationSource(StrEnum):
    USER_ENTERED = "user_entered"
    CLINICIAN_ENTERED = "clinician_entered"
    PRESCRIPTION_CONFIRMED = "prescription_confirmed"


class UserHealthProfile(BaseModel):
    """Minimal health context; direct identifiers intentionally do not belong here."""

    profile_id: UUID = Field(default_factory=uuid4)
    age_years: Annotated[int | None, Field(ge=12, le=60)] = None
    height_cm: Annotated[float | None, Field(gt=100, le=220)] = None
    dietary_preference: DietaryPreference = DietaryPreference.NOT_SPECIFIED
    allergies: list[str] = Field(default_factory=list, max_length=50)
    preferred_language: str = Field(default="en", pattern="^(en|te)$")
    synthetic: bool = True


class PregnancyRecord(BaseModel):
    pregnancy_id: UUID = Field(default_factory=uuid4)
    gestational_week: Annotated[int, Field(ge=0, le=45)]
    estimated_due_date: date | None = None
    known_conditions: list[str] = Field(default_factory=list, max_length=50)
    weight_kg: Annotated[float | None, Field(gt=20, le=300)] = None
    clinician_restrictions: list[str] = Field(default_factory=list, max_length=50)
    synthetic: bool = True


class MedicationRecord(BaseModel):
    medication_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    dose_text: str | None = Field(default=None, max_length=200)
    schedule_text: str | None = Field(default=None, max_length=300)
    source: MedicationSource
    confirmed: bool = False
    active: bool = True
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    synthetic: bool = True

    @model_validator(mode="after")
    def prescription_source_requires_confirmation(self) -> "MedicationRecord":
        if self.source is MedicationSource.PRESCRIPTION_CONFIRMED and not self.confirmed:
            raise ValueError("Prescription-confirmed medication records must be confirmed")
        return self


class AppointmentRecord(BaseModel):
    appointment_id: UUID = Field(default_factory=uuid4)
    scheduled_at: datetime
    purpose: str | None = Field(default=None, max_length=300)
    status: str = Field(default="scheduled", pattern="^(scheduled|completed|cancelled)$")
    notes: str | None = Field(default=None, max_length=1_000)
    synthetic: bool = True
