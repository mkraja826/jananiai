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
    prefer: str | None = None,
    content_type: str = "application/json",
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
    assert response.status_code in {400, 401, 403, 404}, response.text


def current_user_id(token: str) -> str:
    assert SUPABASE_URL is not None
    response = httpx.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers=headers(token),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["id"]


def insert_pregnancy(token: str, owner_id: str, *, week: int = 20) -> str:
    pregnancy_id = str(uuid4())
    response = httpx.post(
        rest_url("pregnancies"),
        headers=headers(token, prefer="return=representation"),
        json={
            "id": pregnancy_id,
            "user_id": owner_id,
            "gestational_week": week,
            "known_conditions": ["synthetic local RLS record"],
        },
        timeout=20,
    )
    response.raise_for_status()
    return pregnancy_id


def insert_attachment(token: str, owner_id: str, pregnancy_id: str) -> str:
    """Create a verified synthetic attachment through the real secure upload handshake."""

    assert SUPABASE_URL is not None
    content = b"%PDF-1.4 synthetic local RLS attachment fixture"
    digest = hashlib.sha256(content).hexdigest()
    intent_response = httpx.post(
        rest_url("rpc/request_janani_attachment_upload"),
        headers=headers(token),
        json={
            "p_pregnancy_id": pregnancy_id,
            "p_kind": "lab_report",
            "p_mime_type": "application/pdf",
            "p_file_size_bytes": len(content),
            "p_content_sha256": digest,
            "p_document_date": "2026-08-07",
            "p_display_label": "Synthetic local fixture",
            "p_capture_source": "file_upload",
            "p_synthetic": True,
        },
        timeout=20,
    )
    intent_response.raise_for_status()
    intent = intent_response.json()
    assert intent["storage_object_path"].startswith(f"{owner_id}/uploads/")

    object_url = (
        f"{SUPABASE_URL}/storage/v1/object/{intent['bucket_id']}/{intent['storage_object_path']}"
    )
    upload = httpx.post(
        object_url,
        headers=headers(token, content_type="application/pdf"),
        content=content,
        timeout=20,
    )
    upload.raise_for_status()

    finalize = httpx.post(
        rest_url("rpc/finalize_janani_attachment_upload"),
        headers=headers(token),
        json={"p_intent_id": intent["id"]},
        timeout=20,
    )
    finalize.raise_for_status()
    attachment = finalize.json()

    verified = httpx.post(
        rest_url("rpc/verify_janani_attachment_integrity"),
        headers=service_headers(),
        json={"p_attachment_id": attachment["id"], "p_actual_sha256": digest},
        timeout=20,
    )
    verified.raise_for_status()
    assert verified.json() == "verified"
    return attachment["id"]


def test_tokens_resolve_to_distinct_synthetic_users() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN and USER_A_ID and USER_B_ID
    assert current_user_id(USER_A_TOKEN) == USER_A_ID
    assert current_user_id(USER_B_TOKEN) == USER_B_ID
    assert USER_A_ID != USER_B_ID


def test_profile_and_pregnancy_rows_are_owner_isolated() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN and USER_A_ID
    profile = httpx.post(
        rest_url("user_health_profiles"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "user_id": USER_A_ID,
            "preferred_language": "en",
            "dietary_preference": "vegetarian",
            "allergies": ["synthetic allergy"],
        },
        timeout=20,
    )
    profile.raise_for_status()

    profile_cross_read = httpx.get(
        rest_url("user_health_profiles"),
        headers=headers(USER_B_TOKEN),
        params={"select": "user_id", "user_id": f"eq.{USER_A_ID}"},
        timeout=20,
    )
    profile_cross_read.raise_for_status()
    assert profile_cross_read.json() == []

    pregnancy_id = insert_pregnancy(USER_A_TOKEN, USER_A_ID)
    pregnancy_cross_read = httpx.get(
        rest_url("pregnancies"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id", "id": f"eq.{pregnancy_id}"},
        timeout=20,
    )
    pregnancy_cross_read.raise_for_status()
    assert pregnancy_cross_read.json() == []

    cross_write = httpx.post(
        rest_url("pregnancies"),
        headers=headers(USER_B_TOKEN),
        json={"id": str(uuid4()), "user_id": USER_A_ID, "gestational_week": 21},
        timeout=20,
    )
    assert_denied(cross_write)


def test_consent_history_is_append_only() -> None:
    assert USER_A_TOKEN and USER_A_ID
    consent_id = str(uuid4())
    created = httpx.post(
        rest_url("consent_events"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "id": consent_id,
            "user_id": USER_A_ID,
            "purpose": "ai_processing",
            "status": "granted",
            "policy_version": "synthetic-local-v1",
            "metadata": {"synthetic": True},
        },
        timeout=20,
    )
    created.raise_for_status()

    updated = httpx.patch(
        rest_url("consent_events"),
        headers=headers(USER_A_TOKEN),
        params={"id": f"eq.{consent_id}"},
        json={"status": "revoked"},
        timeout=20,
    )
    assert_denied(updated)

    deleted = httpx.delete(
        rest_url("consent_events"),
        headers=headers(USER_A_TOKEN),
        params={"id": f"eq.{consent_id}"},
        timeout=20,
    )
    assert_denied(deleted)


def test_related_records_cannot_link_to_another_users_pregnancy() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN and USER_A_ID and USER_B_ID
    pregnancy_id = insert_pregnancy(USER_A_TOKEN, USER_A_ID, week=22)
    attempts = [
        (
            "medication_records",
            {
                "user_id": USER_B_ID,
                "pregnancy_id": pregnancy_id,
                "name": "Synthetic medication",
                "source": "user_entered",
                "confirmed": True,
            },
        ),
        (
            "appointment_records",
            {
                "user_id": USER_B_ID,
                "pregnancy_id": pregnancy_id,
                "scheduled_at": "2026-08-10T10:00:00Z",
                "purpose": "Synthetic appointment",
            },
        ),
        (
            "attachment_records",
            {
                "user_id": USER_B_ID,
                "pregnancy_id": pregnancy_id,
                "kind": "lab_report",
                "mime_type": "application/pdf",
                "storage_object_path": f"{USER_B_ID}/{uuid4()}.pdf",
            },
        ),
    ]
    for table, payload in attempts:
        response = httpx.post(
            rest_url(table),
            headers=headers(USER_B_TOKEN),
            json=payload,
            timeout=20,
        )
        assert_denied(response)


def test_internal_tables_reject_direct_authenticated_writes() -> None:
    assert USER_A_TOKEN and USER_A_ID
    pregnancy_id = insert_pregnancy(USER_A_TOKEN, USER_A_ID, week=23)
    attachment_id = insert_attachment(USER_A_TOKEN, USER_A_ID, pregnancy_id)
    attempts = [
        (
            "context_assembly_events",
            {
                "task": "general_question",
                "status": "ready",
                "excluded_item_count": 0,
                "synthetic": True,
            },
        ),
        (
            "safety_audit_events",
            {
                "request_id": str(uuid4()),
                "ruleset_version": "synthetic",
                "severity": "routine",
                "blocks_llm": False,
                "synthetic": True,
            },
        ),
        (
            "attachment_extractions",
            {
                "attachment_id": attachment_id,
                "extractor_name": "synthetic",
                "extractor_version": "1",
                "extracted_text": "Direct user write must fail",
            },
        ),
        ("account_deletion_requests", {"user_id": USER_A_ID}),
    ]
    for table, payload in attempts:
        response = httpx.post(
            rest_url(table),
            headers=headers(USER_A_TOKEN),
            json=payload,
            timeout=20,
        )
        assert_denied(response)


def test_authenticated_audit_rpcs_are_owner_scoped() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN
    safety_request_id = str(uuid4())
    safety = httpx.post(
        rest_url("rpc/record_janani_safety_event"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_request_id": safety_request_id,
            "p_ruleset_version": "synthetic-local-rules",
            "p_triggered_rule_ids": [],
            "p_severity": "routine",
            "p_blocks_llm": False,
            "p_synthetic": True,
        },
        timeout=20,
    )
    safety.raise_for_status()
    UUID(safety.json())

    context_event_id = str(uuid4())
    context = httpx.post(
        rest_url("rpc/record_janani_context_event"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_event_id": context_event_id,
            "p_task": "general_question",
            "p_status": "ready",
            "p_safety_event_id": safety_request_id,
            "p_selected_medication_ids": [],
            "p_selected_appointment_ids": [],
            "p_selected_attachment_ids": [],
            "p_selected_knowledge_ids": [],
            "p_excluded_item_count": 0,
            "p_schema_version": "1.0",
            "p_synthetic": True,
        },
        timeout=20,
    )
    context.raise_for_status()
    assert context.json() == context_event_id

    owner_read = httpx.get(
        rest_url("context_assembly_events"),
        headers=headers(USER_A_TOKEN),
        params={"select": "id,task,status", "id": f"eq.{context_event_id}"},
        timeout=20,
    )
    owner_read.raise_for_status()
    assert owner_read.json() == [
        {"id": context_event_id, "task": "general_question", "status": "ready"}
    ]

    cross_read = httpx.get(
        rest_url("context_assembly_events"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id", "id": f"eq.{context_event_id}"},
        timeout=20,
    )
    cross_read.raise_for_status()
    assert cross_read.json() == []


def test_extraction_worker_and_user_confirmation_are_separated() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN and USER_A_ID
    pregnancy_id = insert_pregnancy(USER_A_TOKEN, USER_A_ID, week=24)
    attachment_id = insert_attachment(USER_A_TOKEN, USER_A_ID, pregnancy_id)
    extraction_id = str(uuid4())
    rpc_payload = {
        "p_extraction_id": extraction_id,
        "p_attachment_id": attachment_id,
        "p_extractor_name": "synthetic-local-extractor",
        "p_extractor_version": "1.0",
        "p_extracted_text": "Synthetic confirmed report text",
        "p_confidence": 0.99,
    }

    user_worker_call = httpx.post(
        rest_url("rpc/record_janani_attachment_extraction"),
        headers=headers(USER_A_TOKEN),
        json=rpc_payload,
        timeout=20,
    )
    assert_denied(user_worker_call)

    worker_call = httpx.post(
        rest_url("rpc/record_janani_attachment_extraction"),
        headers=service_headers(),
        json=rpc_payload,
        timeout=20,
    )
    worker_call.raise_for_status()
    assert worker_call.json() == extraction_id

    extracted = httpx.get(
        rest_url("attachment_records"),
        headers=headers(USER_A_TOKEN),
        params={
            "select": "extraction_status,confirmation_status",
            "id": f"eq.{attachment_id}",
        },
        timeout=20,
    )
    extracted.raise_for_status()
    assert extracted.json() == [
        {"extraction_status": "completed", "confirmation_status": "unconfirmed"}
    ]

    cross_confirm = httpx.post(
        rest_url("rpc/confirm_janani_attachment_extraction"),
        headers=headers(USER_B_TOKEN),
        json={
            "p_attachment_id": attachment_id,
            "p_extraction_id": extraction_id,
            "p_confirmation": "confirmed",
        },
        timeout=20,
    )
    assert_denied(cross_confirm)

    owner_confirm = httpx.post(
        rest_url("rpc/confirm_janani_attachment_extraction"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_attachment_id": attachment_id,
            "p_extraction_id": extraction_id,
            "p_confirmation": "confirmed",
        },
        timeout=20,
    )
    owner_confirm.raise_for_status()

    confirmed = httpx.get(
        rest_url("attachment_records"),
        headers=headers(USER_A_TOKEN),
        params={"select": "confirmation_status", "id": f"eq.{attachment_id}"},
        timeout=20,
    )
    confirmed.raise_for_status()
    assert confirmed.json() == [{"confirmation_status": "confirmed"}]


def test_private_storage_paths_are_owner_scoped() -> None:
    assert SUPABASE_URL and USER_A_TOKEN and USER_B_TOKEN and USER_A_ID
    object_path = f"{USER_A_ID}/{uuid4()}.pdf"
    object_url = f"{SUPABASE_URL}/storage/v1/object/janani-private/{object_path}"
    payload = b"%PDF-1.4 synthetic local storage object"
    uploaded = httpx.post(
        object_url,
        headers=headers(USER_A_TOKEN, content_type="application/pdf"),
        content=payload,
        timeout=20,
    )
    uploaded.raise_for_status()

    owner_read = httpx.get(object_url, headers=headers(USER_A_TOKEN), timeout=20)
    owner_read.raise_for_status()
    assert owner_read.content == payload

    cross_read = httpx.get(object_url, headers=headers(USER_B_TOKEN), timeout=20)
    assert_denied(cross_read)

    cross_upload = httpx.post(
        f"{SUPABASE_URL}/storage/v1/object/janani-private/{USER_A_ID}/{uuid4()}.pdf",
        headers=headers(USER_B_TOKEN, content_type="application/pdf"),
        content=b"%PDF-1.4 must be rejected",
        timeout=20,
    )
    assert_denied(cross_upload)


def test_account_deletion_request_is_idempotent_and_private() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN
    first = httpx.post(
        rest_url("rpc/request_janani_account_deletion"),
        headers=headers(USER_A_TOKEN),
        json={},
        timeout=20,
    )
    first.raise_for_status()
    first_payload = first.json()
    assert first_payload["status"] == "pending"
    UUID(first_payload["request_id"])

    second = httpx.post(
        rest_url("rpc/request_janani_account_deletion"),
        headers=headers(USER_A_TOKEN),
        json={},
        timeout=20,
    )
    second.raise_for_status()
    assert second.json()["request_id"] == first_payload["request_id"]

    owner_read = httpx.get(
        rest_url("account_deletion_requests"),
        headers=headers(USER_A_TOKEN),
        params={"select": "id,status"},
        timeout=20,
    )
    owner_read.raise_for_status()
    assert owner_read.json() == [{"id": first_payload["request_id"], "status": "pending"}]

    cross_read = httpx.get(
        rest_url("account_deletion_requests"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id,status"},
        timeout=20,
    )
    cross_read.raise_for_status()
    assert cross_read.json() == []
