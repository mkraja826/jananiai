import hashlib
import os
from uuid import UUID, uuid4

import httpx
import pytest

SUPABASE_URL = os.getenv("JANANI_STAGING_SUPABASE_URL")
PUBLISHABLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_PUBLISHABLE_KEY")
SERVICE_ROLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_SERVICE_ROLE_KEY")
USER_A_ID = os.getenv("JANANI_STAGING_USER_A_ID")
USER_A_TOKEN = os.getenv("JANANI_STAGING_USER_A_TOKEN")
USER_B_ID = os.getenv("JANANI_STAGING_USER_B_ID")
USER_B_TOKEN = os.getenv("JANANI_STAGING_USER_B_TOKEN")

_REQUIRED = [
    SUPABASE_URL,
    PUBLISHABLE_KEY,
    SERVICE_ROLE_KEY,
    USER_A_ID,
    USER_A_TOKEN,
    USER_B_ID,
    USER_B_TOKEN,
]

pytestmark = [
    pytest.mark.staging,
    pytest.mark.skipif(
        not all(_REQUIRED),
        reason="Dedicated synthetic Supabase staging credentials are not configured",
    ),
]


def headers(
    token: str,
    *,
    api_key: str | None = None,
    content_type: str = "application/json",
    prefer: str | None = None,
) -> dict[str, str]:
    result = {
        "apikey": api_key or PUBLISHABLE_KEY or "",
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }
    if prefer:
        result["Prefer"] = prefer
    return result


def service_headers(*, prefer: str | None = None) -> dict[str, str]:
    key = SERVICE_ROLE_KEY or ""
    return headers(key, api_key=key, prefer=prefer)


def rest_url(path: str) -> str:
    assert SUPABASE_URL is not None
    return f"{SUPABASE_URL}/rest/v1/{path}"


def assert_denied(response: httpx.Response) -> None:
    assert response.status_code in {400, 401, 403, 404, 409}, response.text


def insert_pregnancy() -> str:
    assert USER_A_TOKEN and USER_A_ID
    pregnancy_id = str(uuid4())
    response = httpx.post(
        rest_url("pregnancies"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "id": pregnancy_id,
            "user_id": USER_A_ID,
            "gestational_week": 39,
            "synthetic": True,
        },
        timeout=20,
    )
    response.raise_for_status()
    return pregnancy_id


def test_pregnancy_completion_is_owner_scoped_append_only_and_correctable() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN
    pregnancy_id = insert_pregnancy()

    cross_completion = httpx.post(
        rest_url("rpc/record_janani_pregnancy_completion"),
        headers=headers(USER_B_TOKEN),
        json={
            "p_pregnancy_id": pregnancy_id,
            "p_occurred_at": "2026-08-07T11:00:00Z",
            "p_completion_type": "delivery",
            "p_source": "user_entered",
            "p_confirmed": True,
            "p_note": "Synthetic cross-user delivery",
            "p_supersedes_completion_event_id": None,
            "p_synthetic": True,
        },
        timeout=20,
    )
    assert_denied(cross_completion)

    first = httpx.post(
        rest_url("rpc/record_janani_pregnancy_completion"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_pregnancy_id": pregnancy_id,
            "p_occurred_at": "2026-08-07T11:00:00Z",
            "p_completion_type": "delivery",
            "p_source": "user_entered",
            "p_confirmed": True,
            "p_note": "Synthetic delivery",
            "p_supersedes_completion_event_id": None,
            "p_synthetic": True,
        },
        timeout=20,
    )
    first.raise_for_status()
    first_payload = first.json()
    UUID(first_payload["id"])

    pregnancy = httpx.get(
        rest_url("pregnancies"),
        headers=headers(USER_A_TOKEN),
        params={"select": "status,completed_at", "id": f"eq.{pregnancy_id}"},
        timeout=20,
    )
    pregnancy.raise_for_status()
    assert pregnancy.json()[0]["status"] == "completed"
    assert pregnancy.json()[0]["completed_at"] is not None

    correction = httpx.post(
        rest_url("rpc/record_janani_pregnancy_completion"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_pregnancy_id": pregnancy_id,
            "p_occurred_at": "2026-08-07T11:05:00Z",
            "p_completion_type": "delivery",
            "p_source": "user_entered",
            "p_confirmed": True,
            "p_note": "Synthetic corrected delivery time",
            "p_supersedes_completion_event_id": first_payload["id"],
            "p_synthetic": True,
        },
        timeout=20,
    )
    correction.raise_for_status()
    assert correction.json()["supersedes_completion_event_id"] == first_payload["id"]

    direct_update = httpx.patch(
        rest_url("pregnancy_completion_events"),
        headers=headers(USER_A_TOKEN),
        params={"id": f"eq.{first_payload['id']}"},
        json={"note": "must not mutate"},
        timeout=20,
    )
    assert_denied(direct_update)

    cross_read = httpx.get(
        rest_url("pregnancy_completion_events"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id", "pregnancy_id": f"eq.{pregnancy_id}"},
        timeout=20,
    )
    cross_read.raise_for_status()
    assert cross_read.json() == []


def test_explicit_reminders_require_owned_confirmed_records_and_rpc_mutation() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN and USER_A_ID
    medication_id = str(uuid4())
    appointment_id = str(uuid4())

    medication = httpx.post(
        rest_url("medication_records"),
        headers=service_headers(prefer="return=representation"),
        json={
            "id": medication_id,
            "user_id": USER_A_ID,
            "name": "Synthetic confirmed medication",
            "source": "clinician_entered",
            "confirmed": True,
            "active": True,
            "synthetic": True,
        },
        timeout=20,
    )
    medication.raise_for_status()

    appointment = httpx.post(
        rest_url("appointment_records"),
        headers=service_headers(prefer="return=representation"),
        json={
            "id": appointment_id,
            "user_id": USER_A_ID,
            "scheduled_at": "2026-08-10T10:00:00Z",
            "purpose": "Synthetic prenatal appointment",
            "status": "scheduled",
            "synthetic": True,
        },
        timeout=20,
    )
    appointment.raise_for_status()

    cross_medication = httpx.post(
        rest_url("rpc/create_janani_medication_reminder"),
        headers=headers(USER_B_TOKEN),
        json={
            "p_medication_id": medication_id,
            "p_local_time": "08:30:00",
            "p_timezone_name": "Asia/Kolkata",
            "p_start_date": "2026-08-07",
            "p_end_date": None,
            "p_weekdays": [1, 2, 3, 4, 5, 6, 7],
            "p_synthetic": True,
        },
        timeout=20,
    )
    assert_denied(cross_medication)

    med_reminder = httpx.post(
        rest_url("rpc/create_janani_medication_reminder"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_medication_id": medication_id,
            "p_local_time": "08:30:00",
            "p_timezone_name": "Asia/Kolkata",
            "p_start_date": "2026-08-07",
            "p_end_date": None,
            "p_weekdays": [1, 3, 5, 7],
            "p_synthetic": True,
        },
        timeout=20,
    )
    med_reminder.raise_for_status()
    med_payload = med_reminder.json()
    assert med_payload["local_time"].startswith("08:30")
    assert med_payload["weekdays"] == [1, 3, 5, 7]

    appointment_reminder = httpx.post(
        rest_url("rpc/create_janani_appointment_reminder"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_appointment_id": appointment_id,
            "p_lead_minutes": 1440,
            "p_synthetic": True,
        },
        timeout=20,
    )
    appointment_reminder.raise_for_status()
    appointment_payload = appointment_reminder.json()
    assert appointment_payload["lead_minutes"] == 1440

    direct_mutation = httpx.patch(
        rest_url("medication_reminder_schedules"),
        headers=headers(USER_A_TOKEN),
        params={"id": f"eq.{med_payload['id']}"},
        json={"local_time": "09:30:00"},
        timeout=20,
    )
    assert_denied(direct_mutation)

    disabled = httpx.post(
        rest_url("rpc/disable_janani_reminder"),
        headers=headers(USER_A_TOKEN),
        json={"p_reminder_kind": "medication", "p_reminder_id": med_payload["id"]},
        timeout=20,
    )
    disabled.raise_for_status()
    assert disabled.json()["enabled"] is False

    cross_read = httpx.get(
        rest_url("medication_reminder_schedules"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id", "id": f"eq.{med_payload['id']}"},
        timeout=20,
    )
    cross_read.raise_for_status()
    assert cross_read.json() == []


def test_attachment_upload_intent_hash_verification_and_extraction_gate() -> None:
    assert SUPABASE_URL and USER_A_TOKEN and USER_B_TOKEN
    pregnancy_id = insert_pregnancy()
    content = b"%PDF-1.4 synthetic phase nine attachment"
    digest = hashlib.sha256(content).hexdigest()

    intent_response = httpx.post(
        rest_url("rpc/request_janani_attachment_upload"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_pregnancy_id": pregnancy_id,
            "p_kind": "lab_report",
            "p_mime_type": "application/pdf",
            "p_file_size_bytes": len(content),
            "p_content_sha256": digest,
            "p_document_date": "2026-08-07",
            "p_display_label": "Synthetic phase nine report",
            "p_capture_source": "file_upload",
            "p_synthetic": True,
        },
        timeout=20,
    )
    intent_response.raise_for_status()
    intent = intent_response.json()
    assert intent["status"] == "pending"

    cross_finalize = httpx.post(
        rest_url("rpc/finalize_janani_attachment_upload"),
        headers=headers(USER_B_TOKEN),
        json={"p_intent_id": intent["id"]},
        timeout=20,
    )
    assert_denied(cross_finalize)

    object_url = (
        f"{SUPABASE_URL}/storage/v1/object/{intent['bucket_id']}/{intent['storage_object_path']}"
    )
    upload = httpx.post(
        object_url,
        headers=headers(USER_A_TOKEN, content_type="application/pdf"),
        content=content,
        timeout=20,
    )
    upload.raise_for_status()

    finalize = httpx.post(
        rest_url("rpc/finalize_janani_attachment_upload"),
        headers=headers(USER_A_TOKEN),
        json={"p_intent_id": intent["id"]},
        timeout=20,
    )
    finalize.raise_for_status()
    attachment = finalize.json()
    attachment_id = attachment["id"]
    assert attachment["integrity_status"] == "pending_worker_hash"
    assert attachment["upload_intent_id"] == intent["id"]

    overwrite = httpx.put(
        object_url,
        headers=headers(USER_A_TOKEN, content_type="application/pdf"),
        content=b"%PDF-1.4 changed",
        timeout=20,
    )
    assert_denied(overwrite)

    delete = httpx.delete(object_url, headers=headers(USER_A_TOKEN), timeout=20)
    assert_denied(delete)

    direct_attachment_insert = httpx.post(
        rest_url("attachment_records"),
        headers=headers(USER_A_TOKEN),
        json={
            "user_id": USER_A_ID,
            "kind": "lab_report",
            "mime_type": "application/pdf",
            "storage_object_path": f"{USER_A_ID}/bypass.pdf",
        },
        timeout=20,
    )
    assert_denied(direct_attachment_insert)

    extraction_id = str(uuid4())
    extraction_payload = {
        "p_extraction_id": extraction_id,
        "p_attachment_id": attachment_id,
        "p_extractor_name": "synthetic-phase9-extractor",
        "p_extractor_version": "1.0",
        "p_extracted_text": "Synthetic extracted report text",
        "p_confidence": 0.97,
    }
    before_hash = httpx.post(
        rest_url("rpc/record_janani_attachment_extraction"),
        headers=service_headers(),
        json=extraction_payload,
        timeout=20,
    )
    assert_denied(before_hash)

    mismatch = httpx.post(
        rest_url("rpc/verify_janani_attachment_integrity"),
        headers=service_headers(),
        json={"p_attachment_id": attachment_id, "p_actual_sha256": "0" * 64},
        timeout=20,
    )
    mismatch.raise_for_status()
    assert mismatch.json() == "mismatch"

    after_mismatch = httpx.post(
        rest_url("rpc/record_janani_attachment_extraction"),
        headers=service_headers(),
        json=extraction_payload,
        timeout=20,
    )
    assert_denied(after_mismatch)

    verified = httpx.post(
        rest_url("rpc/verify_janani_attachment_integrity"),
        headers=service_headers(),
        json={"p_attachment_id": attachment_id, "p_actual_sha256": digest},
        timeout=20,
    )
    verified.raise_for_status()
    assert verified.json() == "verified"

    extraction = httpx.post(
        rest_url("rpc/record_janani_attachment_extraction"),
        headers=service_headers(),
        json=extraction_payload,
        timeout=20,
    )
    extraction.raise_for_status()
    assert extraction.json() == extraction_id
