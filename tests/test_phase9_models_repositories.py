import asyncio
from datetime import date, time
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from app.attachments import AttachmentKind, AttachmentUploadIntentRequest
from app.attachments.repository import SupabaseAttachmentUploadRepository
from app.auth.models import AuthenticatedUser
from app.reminders.models import MedicationReminderScheduleCreate
from app.reminders.repository import SupabaseReminderRepository

USER_ID = UUID("00000000-0000-0000-0000-000000000901")
PREGNANCY_ID = UUID("00000000-0000-0000-0000-000000000902")
MEDICATION_ID = UUID("00000000-0000-0000-0000-000000000903")
UPLOAD_INTENT_ID = UUID("00000000-0000-0000-0000-000000000904")


class FakeRestClient:
    def __init__(self) -> None:
        self.user = AuthenticatedUser(
            user_id=USER_ID,
            access_token=SecretStr("synthetic-token"),
        )
        self.rpc_calls: list[tuple[str, dict]] = []

    async def rpc(self, function_name: str, payload: dict):
        self.rpc_calls.append((function_name, payload))
        if function_name == "create_janani_medication_reminder":
            return {
                "id": "00000000-0000-0000-0000-000000000905",
                "medication_id": str(MEDICATION_ID),
                "local_time": payload["p_local_time"],
                "timezone_name": payload["p_timezone_name"],
                "start_date": payload["p_start_date"],
                "end_date": payload["p_end_date"],
                "weekdays": payload["p_weekdays"],
                "enabled": True,
                "synthetic": payload["p_synthetic"],
                "created_at": "2026-08-07T10:00:00Z",
            }
        if function_name == "request_janani_attachment_upload":
            return {
                "id": str(UPLOAD_INTENT_ID),
                "pregnancy_id": str(PREGNANCY_ID),
                "kind": payload["p_kind"],
                "mime_type": payload["p_mime_type"],
                "file_size_bytes": payload["p_file_size_bytes"],
                "content_sha256": payload["p_content_sha256"],
                "document_date": payload["p_document_date"],
                "display_label": payload["p_display_label"],
                "capture_source": payload["p_capture_source"],
                "synthetic": payload["p_synthetic"],
                "bucket_id": "janani-private",
                "storage_object_path": f"{USER_ID}/uploads/{UPLOAD_INTENT_ID}",
                "status": "pending",
                "expires_at": "2026-08-07T10:15:00Z",
                "created_at": "2026-08-07T10:00:00Z",
            }
        raise AssertionError(f"Unexpected RPC {function_name}")


def user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=USER_ID,
        access_token=SecretStr("synthetic-token"),
    )


def test_medication_reminder_requires_valid_timezone_and_unique_weekdays() -> None:
    schedule = MedicationReminderScheduleCreate(
        medication_id=MEDICATION_ID,
        local_time=time(8, 30),
        timezone_name="Asia/Kolkata",
        start_date=date(2026, 8, 7),
        weekdays=[1, 3, 5],
    )
    assert schedule.weekdays == [1, 3, 5]

    with pytest.raises(ValidationError):
        MedicationReminderScheduleCreate(
            medication_id=MEDICATION_ID,
            local_time=time(8, 30),
            timezone_name="Not/A_Timezone",
            start_date=date(2026, 8, 7),
        )

    with pytest.raises(ValidationError):
        MedicationReminderScheduleCreate(
            medication_id=MEDICATION_ID,
            local_time=time(8, 30),
            timezone_name="Asia/Kolkata",
            start_date=date(2026, 8, 7),
            weekdays=[1, 1],
        )


def test_reminder_repository_preserves_explicit_user_schedule() -> None:
    client = FakeRestClient()
    repository = SupabaseReminderRepository(client)
    payload = MedicationReminderScheduleCreate(
        medication_id=MEDICATION_ID,
        local_time=time(21, 15),
        timezone_name="Asia/Kolkata",
        start_date=date(2026, 8, 7),
        weekdays=[2, 4, 6],
    )

    reminder = asyncio.run(repository.create_medication_reminder(user(), payload))

    assert reminder.local_time == time(21, 15)
    assert reminder.weekdays == [2, 4, 6]
    assert client.rpc_calls[0][1]["p_local_time"] == "21:15:00"
    assert "dose" not in repr(client.rpc_calls[0][1]).lower()


def test_upload_intent_rejects_unsupported_mime_and_oversized_file() -> None:
    valid = AttachmentUploadIntentRequest(
        pregnancy_id=PREGNANCY_ID,
        kind=AttachmentKind.LAB_REPORT,
        mime_type="Application/PDF",
        file_size_bytes=1024,
        content_sha256="A" * 64,
    )
    assert valid.mime_type == "application/pdf"
    assert valid.content_sha256 == "a" * 64

    with pytest.raises(ValidationError):
        AttachmentUploadIntentRequest(
            pregnancy_id=PREGNANCY_ID,
            kind=AttachmentKind.LAB_REPORT,
            mime_type="text/plain",
            file_size_bytes=1024,
            content_sha256="a" * 64,
        )

    with pytest.raises(ValidationError):
        AttachmentUploadIntentRequest(
            pregnancy_id=PREGNANCY_ID,
            kind=AttachmentKind.LAB_REPORT,
            mime_type="application/pdf",
            file_size_bytes=20 * 1024 * 1024 + 1,
            content_sha256="a" * 64,
        )


def test_upload_repository_returns_one_time_owner_scoped_path() -> None:
    client = FakeRestClient()
    repository = SupabaseAttachmentUploadRepository(client)
    payload = AttachmentUploadIntentRequest(
        pregnancy_id=PREGNANCY_ID,
        kind=AttachmentKind.LAB_REPORT,
        mime_type="application/pdf",
        file_size_bytes=2048,
        content_sha256="b" * 64,
        display_label="Synthetic lab report",
    )

    intent = asyncio.run(repository.request_upload(user(), payload))

    assert intent.intent_id == UPLOAD_INTENT_ID
    assert intent.storage_object_path.startswith(f"{USER_ID}/uploads/")
    assert intent.bucket == "janani-private"
    assert client.rpc_calls[0][0] == "request_janani_attachment_upload"
