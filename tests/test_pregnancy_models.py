from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.attachments import AttachmentRegistration, AttachmentSummary
from app.pregnancy.models import (
    EncounterType,
    ObservationKind,
    PregnancyDatingSource,
    PregnancyEncounterCreate,
    PregnancyEpisode,
    PregnancyObservationCreate,
    RecordSource,
)

PREGNANCY_ID = UUID("00000000-0000-0000-0000-000000000801")
ATTACHMENT_ID = UUID("00000000-0000-0000-0000-000000000802")


def test_episode_requires_reference_for_recorded_dating_source() -> None:
    with pytest.raises(ValidationError):
        PregnancyEpisode(
            pregnancy_id=PREGNANCY_ID,
            gestational_week=18,
            dating_source=PregnancyDatingSource.USER_REPORTED_LMP,
        )

    episode = PregnancyEpisode(
        pregnancy_id=PREGNANCY_ID,
        gestational_week=18,
        last_menstrual_period=date(2026, 4, 1),
        dating_source=PregnancyDatingSource.USER_REPORTED_LMP,
    )
    assert episode.last_menstrual_period == date(2026, 4, 1)


def test_observation_shapes_are_typed_without_interpretation() -> None:
    weight = PregnancyObservationCreate(
        pregnancy_id=PREGNANCY_ID,
        kind=ObservationKind.WEIGHT,
        weight_kg=62.5,
    )
    pressure = PregnancyObservationCreate(
        pregnancy_id=PREGNANCY_ID,
        kind=ObservationKind.BLOOD_PRESSURE,
        systolic_mm_hg=120,
        diastolic_mm_hg=80,
    )
    lab = PregnancyObservationCreate(
        pregnancy_id=PREGNANCY_ID,
        kind=ObservationKind.LAB_RESULT,
        label="Synthetic analyte",
        value_text="4.2",
        unit="synthetic-unit",
    )

    assert weight.weight_kg == 62.5
    assert pressure.systolic_mm_hg == 120
    assert lab.label == "Synthetic analyte"

    with pytest.raises(ValidationError):
        PregnancyObservationCreate(
            pregnancy_id=PREGNANCY_ID,
            kind=ObservationKind.LAB_RESULT,
        )


def test_document_confirmed_records_require_attachment_and_confirmation() -> None:
    with pytest.raises(ValidationError):
        PregnancyObservationCreate(
            pregnancy_id=PREGNANCY_ID,
            kind=ObservationKind.LAB_RESULT,
            label="Synthetic analyte",
            value_text="normal-looking text",
            source=RecordSource.DOCUMENT_CONFIRMED,
        )

    observation = PregnancyObservationCreate(
        pregnancy_id=PREGNANCY_ID,
        kind=ObservationKind.LAB_RESULT,
        label="Synthetic analyte",
        value_text="4.2",
        source=RecordSource.DOCUMENT_CONFIRMED,
        confirmed=True,
        source_attachment_id=ATTACHMENT_ID,
    )
    assert observation.confirmed is True


def test_encounter_follow_up_cannot_precede_encounter() -> None:
    occurred_at = datetime(2026, 8, 7, 10, tzinfo=UTC)
    with pytest.raises(ValidationError):
        PregnancyEncounterCreate(
            pregnancy_id=PREGNANCY_ID,
            occurred_at=occurred_at,
            next_follow_up_at=occurred_at - timedelta(days=1),
            encounter_type=EncounterType.ROUTINE_VISIT,
        )


def test_attachment_timeline_metadata_excludes_extracted_text() -> None:
    registration = AttachmentRegistration(
        pregnancy_id=PREGNANCY_ID,
        kind="lab_report",
        mime_type="application/pdf",
        storage_object_path="00000000-0000-0000-0000-000000000999/report.pdf",
        content_sha256="a" * 64,
    )
    assert registration.content_sha256 == "a" * 64
    assert "extracted_text" not in AttachmentSummary.model_fields
