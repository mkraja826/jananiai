from datetime import UTC, datetime, time

from app.attachments import AttachmentSummary
from app.domain import AppointmentRecord
from app.pregnancy.models import (
    ObservationKind,
    PregnancyCompletionEvent,
    PregnancyEncounter,
    PregnancyEpisode,
    PregnancyObservation,
    PregnancyTimeline,
    PregnancyTimelineItem,
    TimelineItemKind,
)


def _date_to_datetime(value) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def build_pregnancy_timeline(
    *,
    pregnancy: PregnancyEpisode,
    observations: list[PregnancyObservation],
    encounters: list[PregnancyEncounter],
    appointments: list[AppointmentRecord],
    attachments: list[AttachmentSummary],
    completions: list[PregnancyCompletionEvent] | None = None,
) -> PregnancyTimeline:
    """Merge structured records chronologically without interpreting clinical meaning."""

    items: list[PregnancyTimelineItem] = []

    for observation in observations:
        if observation.kind is ObservationKind.WEIGHT:
            title = "Weight recorded"
            detail = f"{observation.weight_kg:g} kg" if observation.weight_kg is not None else None
        elif observation.kind is ObservationKind.BLOOD_PRESSURE:
            title = "Blood pressure recorded"
            detail = (
                f"{observation.systolic_mm_hg}/{observation.diastolic_mm_hg} mmHg"
                if observation.systolic_mm_hg is not None
                and observation.diastolic_mm_hg is not None
                else None
            )
        else:
            title = observation.label or "Lab result recorded"
            unit = f" {observation.unit}" if observation.unit else ""
            detail = f"{observation.value_text}{unit}" if observation.value_text else None

        items.append(
            PregnancyTimelineItem(
                item_id=observation.observation_id,
                kind=TimelineItemKind.OBSERVATION,
                occurred_at=observation.observed_at,
                title=title,
                detail=detail,
                source_attachment_id=observation.source_attachment_id,
            )
        )

    for encounter in encounters:
        items.append(
            PregnancyTimelineItem(
                item_id=encounter.encounter_id,
                kind=TimelineItemKind.ENCOUNTER,
                occurred_at=encounter.occurred_at,
                title=encounter.encounter_type.value.replace("_", " ").title(),
                detail=encounter.summary,
                source_attachment_id=encounter.source_attachment_id,
            )
        )

    for appointment in appointments:
        items.append(
            PregnancyTimelineItem(
                item_id=appointment.appointment_id,
                kind=TimelineItemKind.APPOINTMENT,
                occurred_at=appointment.scheduled_at,
                title=appointment.purpose or "Appointment",
                detail=appointment.status,
            )
        )

    for attachment in attachments:
        occurred_at = (
            _date_to_datetime(attachment.document_date)
            if attachment.document_date is not None
            else attachment.created_at
        )
        if occurred_at is None:
            continue
        items.append(
            PregnancyTimelineItem(
                item_id=attachment.attachment_id,
                kind=TimelineItemKind.ATTACHMENT,
                occurred_at=occurred_at,
                title=attachment.display_label or attachment.kind.value.replace("_", " ").title(),
                detail=attachment.confirmation_status.value,
                source_attachment_id=attachment.attachment_id,
            )
        )

    for completion in completions or []:
        title = (
            "Delivery recorded"
            if completion.completion_type.value == "delivery"
            else "Pregnancy completion recorded"
        )
        items.append(
            PregnancyTimelineItem(
                item_id=completion.completion_event_id,
                kind=TimelineItemKind.COMPLETION,
                occurred_at=completion.occurred_at,
                title=title,
                detail=completion.note or completion.completion_type.value.replace("_", " "),
            )
        )

    items.sort(key=lambda item: item.occurred_at, reverse=True)
    return PregnancyTimeline(pregnancy=pregnancy, items=items)
