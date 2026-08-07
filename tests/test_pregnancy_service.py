from datetime import UTC, date, datetime
from uuid import UUID

from app.attachments import (
    AttachmentKind,
    AttachmentSummary,
    ConfirmationStatus,
    ExtractionStatus,
)
from app.domain import AppointmentRecord
from app.pregnancy.models import (
    EncounterType,
    ObservationKind,
    PregnancyEncounter,
    PregnancyEpisode,
    PregnancyObservation,
)
from app.pregnancy.service import build_pregnancy_timeline

PREGNANCY_ID = UUID("00000000-0000-0000-0000-000000000811")


def test_timeline_merges_records_without_clinical_interpretation() -> None:
    pregnancy = PregnancyEpisode(
        pregnancy_id=PREGNANCY_ID,
        gestational_week=20,
    )
    observation = PregnancyObservation(
        observation_id=UUID("00000000-0000-0000-0000-000000000812"),
        pregnancy_id=PREGNANCY_ID,
        kind=ObservationKind.BLOOD_PRESSURE,
        observed_at=datetime(2026, 8, 7, 9, tzinfo=UTC),
        systolic_mm_hg=120,
        diastolic_mm_hg=80,
    )
    encounter = PregnancyEncounter(
        encounter_id=UUID("00000000-0000-0000-0000-000000000813"),
        pregnancy_id=PREGNANCY_ID,
        occurred_at=datetime(2026, 8, 7, 11, tzinfo=UTC),
        encounter_type=EncounterType.ROUTINE_VISIT,
        summary="Synthetic visit summary",
    )
    appointment = AppointmentRecord(
        appointment_id=UUID("00000000-0000-0000-0000-000000000814"),
        scheduled_at=datetime(2026, 8, 8, 10, tzinfo=UTC),
        purpose="Synthetic appointment",
    )
    attachment = AttachmentSummary(
        attachment_id=UUID("00000000-0000-0000-0000-000000000815"),
        pregnancy_id=PREGNANCY_ID,
        kind=AttachmentKind.LAB_REPORT,
        mime_type="application/pdf",
        storage_object_path="synthetic/report.pdf",
        extraction_status=ExtractionStatus.NOT_STARTED,
        confirmation_status=ConfirmationStatus.UNCONFIRMED,
        document_date=date(2026, 8, 6),
        display_label="Synthetic report",
    )

    timeline = build_pregnancy_timeline(
        pregnancy=pregnancy,
        observations=[observation],
        encounters=[encounter],
        appointments=[appointment],
        attachments=[attachment],
    )

    assert [item.kind.value for item in timeline.items] == [
        "appointment",
        "encounter",
        "observation",
        "attachment",
    ]
    pressure_item = next(item for item in timeline.items if item.kind.value == "observation")
    assert pressure_item.detail == "120/80 mmHg"
    combined = " ".join(
        part for item in timeline.items for part in (item.title, item.detail or "")
    ).lower()
    assert "normal" not in combined
    assert "abnormal" not in combined
