from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PregnancyStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class PregnancyDatingSource(StrEnum):
    UNKNOWN = "unknown"
    USER_REPORTED_LMP = "user_reported_lmp"
    CLINICIAN_ESTIMATED_DUE_DATE = "clinician_estimated_due_date"
    ULTRASOUND_ESTIMATED_DUE_DATE = "ultrasound_estimated_due_date"


class PregnancyEpisode(BaseModel):
    """Structured pregnancy episode metadata without diagnostic interpretation."""

    pregnancy_id: UUID
    gestational_week: Annotated[int, Field(ge=0, le=45)]
    estimated_due_date: date | None = None
    last_menstrual_period: date | None = None
    dating_source: PregnancyDatingSource = PregnancyDatingSource.UNKNOWN
    dating_confirmed: bool = False
    known_conditions: list[str] = Field(default_factory=list, max_length=50)
    weight_kg: Annotated[float | None, Field(gt=20, le=300)] = None
    clinician_restrictions: list[str] = Field(default_factory=list, max_length=50)
    status: PregnancyStatus = PregnancyStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_dating_reference(self) -> "PregnancyEpisode":
        if (
            self.dating_source is PregnancyDatingSource.USER_REPORTED_LMP
            and self.last_menstrual_period is None
        ):
            raise ValueError("User-reported LMP dating requires last_menstrual_period")
        if self.dating_source in {
            PregnancyDatingSource.CLINICIAN_ESTIMATED_DUE_DATE,
            PregnancyDatingSource.ULTRASOUND_ESTIMATED_DUE_DATE,
        } and self.estimated_due_date is None:
            raise ValueError("EDD-based dating requires estimated_due_date")
        if self.dating_confirmed and self.dating_source is PregnancyDatingSource.UNKNOWN:
            raise ValueError("Confirmed dating requires a recorded dating source")
        if self.status is PregnancyStatus.COMPLETED and self.completed_at is None:
            raise ValueError("Completed pregnancy episodes require completed_at")
        return self


class ObservationKind(StrEnum):
    WEIGHT = "weight"
    BLOOD_PRESSURE = "blood_pressure"
    LAB_RESULT = "lab_result"


class RecordSource(StrEnum):
    USER_ENTERED = "user_entered"
    CLINICIAN_ENTERED = "clinician_entered"
    DOCUMENT_CONFIRMED = "document_confirmed"


class PregnancyObservationCreate(BaseModel):
    pregnancy_id: UUID
    kind: ObservationKind
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: RecordSource = RecordSource.USER_ENTERED
    confirmed: bool = False
    weight_kg: Annotated[float | None, Field(gt=20, le=300)] = None
    systolic_mm_hg: Annotated[int | None, Field(gt=0, le=400)] = None
    diastolic_mm_hg: Annotated[int | None, Field(gt=0, le=400)] = None
    label: str | None = Field(default=None, min_length=1, max_length=120)
    value_text: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = Field(default=None, max_length=60)
    source_attachment_id: UUID | None = None
    supersedes_observation_id: UUID | None = None
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_shape(self) -> "PregnancyObservationCreate":
        if self.kind is ObservationKind.WEIGHT and self.weight_kg is None:
            raise ValueError("Weight observations require weight_kg")
        if self.kind is ObservationKind.BLOOD_PRESSURE and (
            self.systolic_mm_hg is None or self.diastolic_mm_hg is None
        ):
            raise ValueError("Blood-pressure observations require systolic and diastolic values")
        if self.kind is ObservationKind.LAB_RESULT and (
            self.label is None or self.value_text is None
        ):
            raise ValueError("Lab-result observations require label and value_text")
        if self.source is RecordSource.DOCUMENT_CONFIRMED and (
            not self.confirmed or self.source_attachment_id is None
        ):
            raise ValueError(
                "Document-confirmed observations require confirmation and source attachment"
            )
        return self


class PregnancyObservation(PregnancyObservationCreate):
    observation_id: UUID = Field(default_factory=uuid4)
    created_at: datetime | None = None


class EncounterType(StrEnum):
    ROUTINE_VISIT = "routine_visit"
    SCAN = "scan"
    LAB_REVIEW = "lab_review"
    PROCEDURE = "procedure"
    OTHER = "other"


class PregnancyEncounterCreate(BaseModel):
    pregnancy_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    encounter_type: EncounterType = EncounterType.ROUTINE_VISIT
    summary: str | None = Field(default=None, max_length=2_000)
    next_follow_up_at: datetime | None = None
    source: RecordSource = RecordSource.USER_ENTERED
    confirmed: bool = False
    source_attachment_id: UUID | None = None
    supersedes_encounter_id: UUID | None = None
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_encounter(self) -> "PregnancyEncounterCreate":
        if self.next_follow_up_at is not None and self.next_follow_up_at < self.occurred_at:
            raise ValueError("next_follow_up_at cannot be earlier than occurred_at")
        if self.source is RecordSource.DOCUMENT_CONFIRMED and (
            not self.confirmed or self.source_attachment_id is None
        ):
            raise ValueError(
                "Document-confirmed encounters require confirmation and source attachment"
            )
        return self


class PregnancyEncounter(PregnancyEncounterCreate):
    encounter_id: UUID = Field(default_factory=uuid4)
    created_at: datetime | None = None


class TimelineItemKind(StrEnum):
    OBSERVATION = "observation"
    ENCOUNTER = "encounter"
    APPOINTMENT = "appointment"
    ATTACHMENT = "attachment"


class PregnancyTimelineItem(BaseModel):
    item_id: UUID
    kind: TimelineItemKind
    occurred_at: datetime
    title: str = Field(min_length=1, max_length=160)
    detail: str | None = Field(default=None, max_length=2_000)
    source_attachment_id: UUID | None = None


class PregnancyTimeline(BaseModel):
    pregnancy: PregnancyEpisode
    items: list[PregnancyTimelineItem] = Field(default_factory=list)
