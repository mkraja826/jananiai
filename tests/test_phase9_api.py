from datetime import date, time
from uuid import UUID

from fastapi.testclient import TestClient

from app.attachments.dependencies import get_attachment_upload_repository
from app.attachments.models import (
    AttachmentIntegrityStatus,
    AttachmentKind,
    AttachmentSummary,
    AttachmentUploadIntent,
    AttachmentUploadIntentRequest,
)
from app.config import Settings
from app.main import create_app
from app.reminders.dependencies import get_reminder_repository
from app.reminders.models import (
    AppointmentReminderSchedule,
    AppointmentReminderScheduleCreate,
    MedicationReminderSchedule,
    MedicationReminderScheduleCreate,
    ReminderOverview,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000911")
PREGNANCY_ID = UUID("00000000-0000-0000-0000-000000000912")
MEDICATION_ID = UUID("00000000-0000-0000-0000-000000000913")
APPOINTMENT_ID = UUID("00000000-0000-0000-0000-000000000914")
UPLOAD_INTENT_ID = UUID("00000000-0000-0000-0000-000000000915")
ATTACHMENT_ID = UUID("00000000-0000-0000-0000-000000000916")


class FakeReminderRepository:
    async def list_reminders(self, user) -> ReminderOverview:
        return ReminderOverview()

    async def create_medication_reminder(self, user, payload: MedicationReminderScheduleCreate):
        return MedicationReminderSchedule(
            reminder_id=UUID("00000000-0000-0000-0000-000000000917"),
            **payload.model_dump(),
        )

    async def create_appointment_reminder(
        self,
        user,
        payload: AppointmentReminderScheduleCreate,
    ):
        return AppointmentReminderSchedule(
            reminder_id=UUID("00000000-0000-0000-0000-000000000918"),
            **payload.model_dump(),
        )

    async def disable_medication_reminder(self, user, reminder_id: UUID):
        return MedicationReminderSchedule(
            reminder_id=reminder_id,
            medication_id=MEDICATION_ID,
            local_time=time(8, 30),
            timezone_name="Asia/Kolkata",
            start_date=date(2026, 8, 7),
            enabled=False,
            disabled_at="2026-08-07T10:00:00Z",
        )

    async def disable_appointment_reminder(self, user, reminder_id: UUID):
        return AppointmentReminderSchedule(
            reminder_id=reminder_id,
            appointment_id=APPOINTMENT_ID,
            lead_minutes=1440,
            enabled=False,
            disabled_at="2026-08-07T10:00:00Z",
        )


class FakeAttachmentUploadRepository:
    async def request_upload(self, user, payload: AttachmentUploadIntentRequest):
        return AttachmentUploadIntent(
            intent_id=UPLOAD_INTENT_ID,
            storage_object_path=f"{USER_ID}/uploads/{UPLOAD_INTENT_ID}",
            expires_at="2026-08-07T10:15:00Z",
            **payload.model_dump(),
        )

    async def finalize_upload(self, user, intent_id: UUID):
        return AttachmentSummary(
            attachment_id=ATTACHMENT_ID,
            pregnancy_id=PREGNANCY_ID,
            kind=AttachmentKind.LAB_REPORT,
            mime_type="application/pdf",
            storage_object_path=f"{USER_ID}/uploads/{intent_id}",
            file_size_bytes=2048,
            content_sha256="a" * 64,
            integrity_status=AttachmentIntegrityStatus.PENDING_WORKER_HASH,
        )


def client() -> TestClient:
    application = create_app(settings=Settings(environment="test", free_first_mode=True))
    application.dependency_overrides[get_reminder_repository] = lambda: FakeReminderRepository()
    application.dependency_overrides[get_attachment_upload_repository] = (
        lambda: FakeAttachmentUploadRepository()
    )
    return TestClient(application)


def test_medication_reminder_api_preserves_explicit_local_schedule() -> None:
    response = client().post(
        "/v1/reminders/medications",
        json={
            "medication_id": str(MEDICATION_ID),
            "local_time": "08:30:00",
            "timezone_name": "Asia/Kolkata",
            "start_date": "2026-08-07",
            "weekdays": [1, 3, 5, 7],
            "synthetic": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["local_time"] == "08:30:00"
    assert payload["timezone_name"] == "Asia/Kolkata"
    assert payload["weekdays"] == [1, 3, 5, 7]


def test_appointment_reminder_api_preserves_user_selected_lead_time() -> None:
    response = client().post(
        "/v1/reminders/appointments",
        json={
            "appointment_id": str(APPOINTMENT_ID),
            "lead_minutes": 1440,
            "synthetic": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["lead_minutes"] == 1440


def test_real_reminder_payload_is_blocked_in_free_first_mode() -> None:
    response = client().post(
        "/v1/reminders/medications",
        json={
            "medication_id": str(MEDICATION_ID),
            "local_time": "08:30:00",
            "timezone_name": "Asia/Kolkata",
            "start_date": "2026-08-07",
            "synthetic": False,
        },
    )

    assert response.status_code == 403
    assert "Real patient data" in response.json()["detail"]


def test_attachment_upload_intent_api_returns_generated_private_path() -> None:
    response = client().post(
        "/v1/attachments/upload-intents",
        json={
            "pregnancy_id": str(PREGNANCY_ID),
            "kind": "lab_report",
            "mime_type": "application/pdf",
            "file_size_bytes": 2048,
            "content_sha256": "A" * 64,
            "display_label": "Synthetic report",
            "synthetic": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["intent_id"] == str(UPLOAD_INTENT_ID)
    assert payload["storage_object_path"].startswith(f"{USER_ID}/uploads/")
    assert payload["content_sha256"] == "a" * 64


def test_attachment_finalize_api_keeps_integrity_pending_for_worker_hash() -> None:
    response = client().post(
        f"/v1/attachments/upload-intents/{UPLOAD_INTENT_ID}/finalize"
    )

    assert response.status_code == 201
    assert response.json()["integrity_status"] == "pending_worker_hash"


def test_real_attachment_upload_intent_is_blocked_in_free_first_mode() -> None:
    response = client().post(
        "/v1/attachments/upload-intents",
        json={
            "pregnancy_id": str(PREGNANCY_ID),
            "kind": "lab_report",
            "mime_type": "application/pdf",
            "file_size_bytes": 2048,
            "content_sha256": "a" * 64,
            "synthetic": False,
        },
    )

    assert response.status_code == 403
    assert "Real patient data" in response.json()["detail"]
